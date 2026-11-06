import base64
import numpy as np
import cv2
import pytest
from app.face_engine import descriptor_from_crop, chi_square, recognize, pack_descriptor, unpack_descriptor, decode_image

def test_descriptor_is_stable_and_roundtrips():
    img=np.random.default_rng(3).integers(0,255,(96,96),dtype=np.uint8)
    a=descriptor_from_crop(img)
    assert a.shape==(16*59,)
    assert np.isclose(chi_square(a,a),0)
    assert np.allclose(a,unpack_descriptor(pack_descriptor(a)))
    for tile in a.reshape(16,59):
        assert np.isclose(tile.sum(),1.0)

def test_recognition_rejects_unknown_and_ambiguous():
    rng=np.random.default_rng(9)
    desc=descriptor_from_crop(rng.integers(0,255,(96,96),dtype=np.uint8))
    sid,ranked=recognize(desc,[('alice',desc)],threshold=.3)
    assert sid=='alice'
    sid,ranked=recognize(desc,[('alice',desc),('bob',desc)],threshold=.3)
    assert sid is None
    sid,ranked=recognize(desc,[],threshold=.3)
    assert sid is None

def test_decode_bad_image():
    with pytest.raises(ValueError):decode_image('xyz_not_base64')
    img=np.zeros((100,100,3),dtype=np.uint8)
    ok,png=cv2.imencode('.png',img)
    assert ok
    decoded=decode_image('data:image/png;base64,'+base64.b64encode(png.tobytes()).decode())
    assert decoded.shape == img.shape
