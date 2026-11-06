"""Traditional offline Haar + uniform LBP face recognition (not a liveness detector).

No external model downloads are required. This is an educational baseline, not an
identity-verification system suitable for real grading decisions or high-stakes use.
"""
import base64
import binascii
import zlib
import numpy as np
import cv2

FACE_SIZE = (96, 96)
GRID = 4
BINS = 59
MAX_PHOTO_BYTES = 4_000_000
_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
if _CASCADE.empty():
    raise RuntimeError('OpenCV face detector is unavailable')

# Uniform LBP has 58 binary 8-neighbour patterns (<=2 circular bit
# transitions), plus one bucket for all non-uniform patterns.
def _make_uniform_mapping():
    m = np.full(256, 58, dtype=np.uint8)
    ix = 0
    for v in range(256):
        bits = [(v >> k) & 1 for k in range(8)]
        transitions = sum(bits[k] != bits[(k + 1) % 8] for k in range(8))
        if transitions <= 2:
            m[v] = ix
            ix += 1
    assert ix == 58
    return m

UNIFORM_LBP = _make_uniform_mapping()

def decode_image(data_uri):
    if not isinstance(data_uri, str) or len(data_uri) > MAX_PHOTO_BYTES * 2:
        raise ValueError('Image is missing or too large (maximum 4 MB)')
    raw_b64 = data_uri.split(',', 1)[-1]
    try:
        raw = base64.b64decode(raw_b64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('Invalid image encoding')
    if not raw or len(raw) > MAX_PHOTO_BYTES:
        raise ValueError('Image must be smaller than 4 MB')
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[0] > 3000 or image.shape[1] > 3000:
        raise ValueError('Invalid image or resolution too large')
    return image

def face_crop(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = _CASCADE.detectMultiScale(gray, scaleFactor=1.09, minNeighbors=7, minSize=(60, 60))
    if len(faces) == 0:
        raise ValueError('No face detected. Face the camera with good lighting.')
    if len(faces) > 1:
        raise ValueError('Multiple faces detected. Only one person should be visible.')
    x, y, w, h = map(int, faces[0])
    crop = gray[y:y+h, x:x+w]
    crop = cv2.resize(crop, FACE_SIZE, interpolation=cv2.INTER_AREA)
    crop = cv2.equalizeHist(crop)
    return crop

def descriptor_from_crop(gray):
    """Deterministic normalized 4x4 grid x 59-bin uniform LBP histogram."""
    if gray.shape != FACE_SIZE:
        raise ValueError('Face crop must be 96 x 96 pixels')
    center = gray[1:-1, 1:-1].astype(np.int16)
    neighbours = [
        gray[:-2, :-2], gray[:-2, 1:-1], gray[:-2, 2:],
        gray[1:-1, 2:], gray[2:, 2:], gray[2:, 1:-1],
        gray[2:, :-2], gray[1:-1, :-2]
    ]
    code = np.zeros(center.shape, dtype=np.uint8)
    for i, n in enumerate(neighbours):
        code |= ((n.astype(np.int16) >= center).astype(np.uint8) << i)
    codes = UNIFORM_LBP[code]
    hist = []
    for part in np.array_split(codes, GRID, axis=0):
        for tile in np.array_split(part, GRID, axis=1):
            v = np.bincount(tile.ravel(), minlength=BINS).astype(np.float32)
            hist.append(v / max(float(v.sum()), 1.0))
    return np.concatenate(hist).astype(np.float32)

def describe_photo(data_uri):
    return descriptor_from_crop(face_crop(decode_image(data_uri)))

def pack_descriptor(array):
    return zlib.compress(np.asarray(array, dtype=np.float32).tobytes(), 6)

def unpack_descriptor(blob):
    result = np.frombuffer(zlib.decompress(blob), dtype=np.float32)
    if result.size != GRID * GRID * BINS:
        raise ValueError('Invalid biometric template length')
    return result

def chi_square(a, b):
    # Average tile chi-square; 0 is identical. Range is approximately 0..1.
    a = np.asarray(a, dtype=np.float32).reshape(GRID * GRID, BINS)
    b = np.asarray(b, dtype=np.float32).reshape(GRID * GRID, BINS)
    return float(np.mean(0.5 * np.sum(((a - b) ** 2) / (a + b + 1e-7), axis=1)))

def rank_matches(probe, templates):
    """templates: iterable of (student_id, descriptor); return sorted best scores."""
    by_student = {}
    for sid, descriptor in templates:
        d = chi_square(probe, descriptor)
        by_student[sid] = min(by_student.get(sid, 2.0), d)
    return sorted(by_student.items(), key=lambda item: item[1])

def recognize(probe, templates, threshold=0.30, margin=0.035):
    """Fail closed if no strong match or not separated from the next identity.

    Threshold is an initial classroom-demo setting; evaluate and calibrate with
    volunteer data before relying on it for any real decisions.
    """
    ordered = rank_matches(probe, templates)
    if not ordered or ordered[0][1] > threshold:
        return None, ordered
    if len(ordered) > 1 and (ordered[1][1] - ordered[0][1]) < margin:
        return None, ordered
    return ordered[0][0], ordered
