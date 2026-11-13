"""Business rules: blockchain is authoritative, SQLite only stores private data."""
import uuid
import sqlite3
from . import db
from .config import env
from .face_engine import describe_photo, pack_descriptor, unpack_descriptor, recognize
from .ledger import token, get_ledger, LedgerError

class BadRequest(ValueError):
    pass

def ledger_checked():
    ledger = get_ledger()
    result = ledger.verify()
    if not result.get('valid'):
        raise LedgerError('Chain verification failed; attendance writes and reads are blocked: ' + result.get('reason', 'unknown'))
    return ledger

def enrol(name, roll, samples, consent):
    name = name.strip()
    roll = roll.strip().upper()
    if not consent:
        raise BadRequest('Student consent is required before collecting biometric templates')
    if not (2 <= len(name) <= 90) or not (2 <= len(roll) <= 24):
        raise BadRequest('Enter a valid student name (2-90) and roll number (2-24 characters)')
    if not all(c.isalnum() or c in '-_/' for c in roll):
        raise BadRequest('Roll numbers may contain letters, numbers, hyphens, underscores and slashes only')
    if not 3 <= len(samples) <= 6:
        raise BadRequest('Take 3 to 6 distinct face photos for registration')
    if len(set(samples)) != len(samples):
        raise BadRequest('Capture different photos instead of reusing the same image')
    descriptors = [describe_photo(s) for s in samples]
    # Consistency is a coarse quality control, not proof of the same identity.
    sid = str(uuid.uuid4())
    when = db.now()
    try:
        with db.connect() as conn:
            conn.execute('INSERT INTO students(id, roll, name, consent_at, enrolled_at) VALUES (?,?,?,?,?)',
                         (sid, roll, name, when, when))
            conn.executemany('INSERT INTO face_templates(student_id, descriptor) VALUES (?,?)',
                             [(sid, pack_descriptor(d)) for d in descriptors])
    except sqlite3.IntegrityError as e:
        raise BadRequest('This roll number is already registered') from e
    return {'id': sid, 'name': name, 'roll': roll, 'templates': len(descriptors)}

def enrol_without_biometrics(name, roll):
    """Faculty-only student record with NO biometric data. Can only use audit-labelled manual attendance."""
    name = name.strip()
    roll = roll.strip().upper()
    if not (2 <= len(name) <= 90) or not (2 <= len(roll) <= 24):
        raise BadRequest('Enter a valid name and roll number')
    if not all(c.isalnum() or c in '-_/' for c in roll):
        raise BadRequest('Roll numbers may contain letters, numbers, hyphens, underscores and slashes only')
    sid = str(uuid.uuid4())
    try:
        with db.connect() as conn:
            conn.execute('INSERT INTO students(id, roll, name, consent_at, enrolled_at) VALUES (?,?,?,?,?)',
                         (sid, roll, name, '', db.now()))
    except sqlite3.IntegrityError as e:
        raise BadRequest('This roll number is already registered') from e
    return {'id': sid, 'name': name, 'roll': roll, 'templates': 0, 'mode': 'manual-only'}


def remove_student(student_id):
    with db.connect() as conn:
        r = conn.execute('SELECT id FROM students WHERE id=?', (student_id,)).fetchone()
        if not r:
            raise BadRequest('Student does not exist')
        conn.execute('DELETE FROM students WHERE id=?', (student_id,))
    return {'deleted': True, 'note': 'Local identity and templates removed. Prior pseudonymous blockchain records cannot be erased.'}

def create_session(title, course):
    title, course = title.strip(), course.strip()
    if not (2 <= len(title) <= 90) or not (2 <= len(course) <= 30):
        raise BadRequest('Session title must be 2-90 characters and course 2-30 characters')
    sid = str(uuid.uuid4())
    chain = ledger_checked()
    receipt = chain.create_session(token('session', sid))
    with db.connect() as conn:
        conn.execute('INSERT INTO class_sessions(id, title, course, created_at, closed_at) VALUES (?,?,?,?,NULL)',
                     (sid, title, course, db.now()))
    return {'id': sid, 'title': title, 'course': course, 'receipt': receipt}

def close_session(sid):
    with db.connect() as conn:
        r = conn.execute('SELECT * FROM class_sessions WHERE id=?',(sid,)).fetchone()
        if not r:
            raise BadRequest('Session does not exist')
        if r['closed_at']:
            raise BadRequest('Session already closed')
    chain = ledger_checked()
    receipt = chain.close_session(token('session', sid))
    with db.connect() as conn:
        conn.execute('UPDATE class_sessions SET closed_at=? WHERE id=?', (db.now(), sid))
    return {'closed': True, 'receipt': receipt}

def recognize_student(photo):
    probe = describe_photo(photo)
    with db.connect() as conn:
        templates = [(r['student_id'], unpack_descriptor(r['descriptor'])) for r in
                     conn.execute('SELECT student_id, descriptor FROM face_templates')]
        if not templates:
            raise BadRequest('Register at least one student first')
        threshold = float(env('FACE_DISTANCE_THRESHOLD', '0.30'))
        margin = float(env('FACE_DISTANCE_MARGIN', '0.035'))
        sid, ranked = recognize(probe, templates, threshold, margin)
        if sid is None:
            return {'recognized': False, 'message': 'Unknown or uncertain face; attendance not marked.',
                    'best_distance': round(ranked[0][1], 4) if ranked else None}
        row = conn.execute('SELECT id, name, roll FROM students WHERE id=?',(sid,)).fetchone()
        if not row:
            raise BadRequest('Recognized student record missing')
        return {'recognized': True, 'student': dict(row), 'distance': round(ranked[0][1], 4),
                'message': 'Face matched. This is not a liveness check.'}

def mark_attendance(sid, photo, expected_student_id=None):
    with db.connect() as conn:
        session = conn.execute('SELECT * FROM class_sessions WHERE id=?', (sid,)).fetchone()
        if not session:
            raise BadRequest('Select a registered class session')
        if session['closed_at']:
            raise BadRequest('This class session has been closed')
    result = recognize_student(photo)
    if not result['recognized']:
        raise BadRequest('Not marked: face is unknown or recognition is uncertain')
    student = result['student']
    if expected_student_id is not None and student['id'] != expected_student_id:
        raise BadRequest('Face did not match the signed-in student account')
    chain = ledger_checked()
    receipt = chain.mark_attendance(token('session', sid), token('student', student['id']))
    return {'marked': True, 'student': student, 'receipt': receipt, 'distance': result['distance']}

def manual_attendance(sid, student_id, reason):
    reason = reason.strip()
    if not (8 <= len(reason) <= 300):
        raise BadRequest('Provide a clear faculty override reason (8-300 characters)')
    with db.connect() as conn:
        student = conn.execute('SELECT id, name, roll FROM students WHERE id=?', (student_id,)).fetchone()
        if not student:
            raise BadRequest('Choose an enrolled student')
        session = conn.execute('SELECT id, closed_at FROM class_sessions WHERE id=?', (sid,)).fetchone()
        if not session or session['closed_at']:
            raise BadRequest('Session missing or closed')
    chain = ledger_checked()
    receipt = chain.manual_attendance(token('session', sid), token('student', student_id), reason)
    return {'marked': True, 'method': 'manual', 'student': dict(student), 'receipt': receipt,
            'note': 'Faculty override explicitly recorded on the ledger; no face match is claimed.'}

def flag_attendance(sid, student_id, reason):
    reason = reason.strip()
    if len(reason) < 5 or len(reason) > 300:
        raise BadRequest('Provide a correction reason (5-300 characters)')
    with db.connect() as conn:
        if not conn.execute('SELECT id FROM students WHERE id=?',(student_id,)).fetchone():
            raise BadRequest('Student does not exist')
        session = conn.execute('SELECT * FROM class_sessions WHERE id=?',(sid,)).fetchone()
        if not session or session['closed_at']:
            raise BadRequest('Session missing or closed')
    chain = ledger_checked()
    receipt = chain.void_attendance(token('session', sid), token('student', student_id), reason)
    return {'flagged': True, 'receipt': receipt,
            'note': 'Original record stays on-chain; a correction event records the flag.'}

def attendance_report(session_id=None):
    chain = ledger_checked()
    events = chain.events()
    students = db.get_students()
    sessions = db.get_sessions()
    stu_tokens = {token('student', student['id']):student for student in students}
    ses_tokens = {token('session', ses['id']):ses for ses in sessions}
    flagged = {(e['session_token'],e.get('student_token')) for e in events if e['type']=='void'}
    rows = []
    for e in events:
        if e['type'] not in ('mark', 'manual'):
            continue
        ses = ses_tokens.get(e['session_token'])
        stu = stu_tokens.get(e.get('student_token'))
        if session_id and (not ses or ses['id'] != session_id):
            continue
        rows.append({
            'session_id': ses['id'] if ses else None,
            'session': ses['title'] if ses else 'Unknown / removed',
            'course': ses['course'] if ses else '—',
            'student_id': stu['id'] if stu else None,
            'student': stu['name'] if stu else '[Deleted student]',
            'roll': stu['roll'] if stu else '—',
            'timestamp': e['timestamp'],
            'tx_hash': e['tx_hash'],
            'block_number': e['block_number'],
            'status': 'Flagged / correction' if (e['session_token'],e.get('student_token')) in flagged else 'Present',
            'method': 'Faculty override' if e['type'] == 'manual' else 'Face scan'
        })
    return list(reversed(rows))

def overview():
    students = db.get_students()
    sessions = db.get_sessions()
    chain = ledger_checked()
    report = attendance_report()
    return {'students': len(students), 'sessions': len(sessions),
            'active_sessions': sum(1 for s in sessions if not s['closed_at']),
            'attendance_marks': sum(1 for r in report if r['status'] == 'Present'),
            'ledger': chain.verify()}

def chain_explorer():
    chain = get_ledger()
    verification = chain.verify()
    events = chain.events() if verification.get('valid') else []
    types = {'create': 'Session created', 'close': 'Session closed', 'mark': 'Face-scan attendance',
             'manual': 'Faculty override attendance', 'void': 'Attendance correction'}
    return {'backend': chain.backend, 'verification': verification,
            'events': [{**e, 'label': types.get(e['type'],e['type']),
                        'student_token': (e.get('student_token') or '')[:12] + '…' if e.get('student_token') else None,
                        'session_token': e['session_token'][:12] + '…'}
                       for e in reversed(events[-50:])]}
