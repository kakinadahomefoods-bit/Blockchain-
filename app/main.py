"""Secure local-only FastAPI server + student attendance web UI."""
import csv
import hashlib
import hmac
import io
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Depends, Response
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from .config import ROOT, env, require_secret
from . import db, service
from .ledger import LedgerError

_sessions = {}
_failed = defaultdict(deque)
_auth_lock = threading.RLock()
SESSION_AGE = 60 * 60 * 8

@asynccontextmanager
async def lifespan(app):
    require_secret('ADMIN_PASSWORD')
    require_secret('HMAC_KEY')
    db.initialize()
    # Do not prevent the read-only diagnostics UI from starting if a prior
    # ledger is corrupt. All attendance mutations still verify first.
    service.get_ledger()
    yield

app = FastAPI(title='BlockAttend - Secure Smart Attendance', docs_url=None, redoc_url=None, lifespan=lifespan)

@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=()'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response

@app.exception_handler(service.BadRequest)
async def bad_request(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=400)

@app.exception_handler(LedgerError)
async def ledger_error(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=409)

class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)

class Enrollment(BaseModel):
    name: str
    roll: str
    consent: bool
    photos: list[str]

class ManualStudentNew(BaseModel):
    name: str
    roll: str

class SessionNew(BaseModel):
    title: str
    course: str

class ImageScan(BaseModel):
    photo: str

class Correction(BaseModel):
    student_id: str
    reason: str

class StudentJoinLookup(BaseModel):
    code: str = Field(min_length=12, max_length=12)

class StudentJoinAttendance(BaseModel):
    code: str = Field(min_length=12, max_length=12)
    photo: str = Field(min_length=100, max_length=5_600_000)

class StudentLoginRequest(BaseModel):
    roll: str = Field(min_length=2, max_length=24)
    password: str = Field(min_length=1, max_length=256)

class StudentChangePassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)

_join_attempts = defaultdict(deque)
_join_lock = threading.RLock()
_student_sessions = {}
_student_attempts = defaultdict(deque)
_student_auth_lock = threading.RLock()
_STUDENT_SESSION_AGE = 60 * 60 * 4
_PASSWORD_ROUNDS = 310_000

def _password_digest(password, salt, rounds=_PASSWORD_ROUNDS):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), rounds).hex()

def _student_session(request):
    sid=request.cookies.get('blockattend_student_sid','')
    with _student_auth_lock:
        session=_student_sessions.get(sid)
        if not session or session['expires']<time.time():
            _student_sessions.pop(sid,None)
            return None
    if not db.get_student_login_by_id(session['student_id']):
        with _student_auth_lock:
            _student_sessions.pop(sid,None)
        return None
    return session

def student_auth(request: Request):
    session=_student_session(request)
    if not session:
        raise HTTPException(401,'Student login required')
    if request.method not in ('GET','HEAD'):
        if not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),session['csrf']):
            raise HTTPException(403,'Invalid student CSRF token')
    return session

def _limit_student_login(request):
    addr=request.client.host if request.client else 'unknown'
    now=time.monotonic()
    with _student_auth_lock:
        attempts=_student_attempts[addr]
        while attempts and attempts[0]<now-600:
            attempts.popleft()
        if len(attempts)>=12:
            raise HTTPException(429,'Too many login attempts. Try again later.')
        attempts.append(now)
        return addr


def _class_join_code(session_id):
    """Stable 12-hex invitation code tied to faculty's existing HMAC key."""
    key = bytes.fromhex(require_secret('HMAC_KEY'))
    return hmac.new(key, ('student-join:' + session_id).encode(), hashlib.sha256).hexdigest()[:12].upper()

def _class_from_join_code(code):
    value = str(code or '').strip().upper()
    if len(value) != 12 or any(c not in '0123456789ABCDEF' for c in value):
        return None
    for course in db.get_sessions():
        if hmac.compare_digest(_class_join_code(course['id']), value):
            return course
    return None

def _limit_student_join(request: Request, maximum=25):
    """Local prototype throttle. Use a distributed limiter for cloud hosting."""
    ip = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    with _join_lock:
        recent = _join_attempts[ip]
        while recent and recent[0] < now - 600:
            recent.popleft()
        if len(recent) >= maximum:
            raise HTTPException(429, 'Too many attempts. Contact faculty.')
        recent.append(now)

def _auth_from_cookie(request):
    cookie = request.cookies.get('blockattend_sid', '')
    with _auth_lock:
        session = _sessions.get(cookie)
        if not session or session['expires'] < time.time():
            _sessions.pop(cookie, None)
            return None
        return session

def auth(request: Request):
    session = _auth_from_cookie(request)
    if not session:
        raise HTTPException(401, 'Log in as the faculty administrator first')
    if request.method not in ('GET','HEAD'):
        csrf = request.headers.get('X-CSRF-Token', '')
        if not hmac.compare_digest(csrf, session['csrf']):
            raise HTTPException(403, 'Invalid CSRF token; refresh the page and log in again')
    return session

@app.get('/health')
def health():
    return {'status': 'ok', 'app': 'BlockAttend'}

@app.get('/')
def homepage():
    return FileResponse(ROOT / 'static' / 'index.html', media_type='text/html')

@app.get('/static/{filename}')
def static_file(filename: str):
    if filename not in ('app.js','styles.css','logo.svg','student-join.js','student-join.css'):
        raise HTTPException(404)
    return FileResponse(ROOT / 'static' / filename)

@app.get('/join')
def student_join():
    return FileResponse(ROOT / 'static' / 'join.html', media_type='text/html')

@app.post('/api/student/login')
def login_student(payload: StudentLoginRequest, request: Request, response: Response):
    addr=_limit_student_login(request)
    account=db.student_login_record(payload.roll)
    salt=account['password_salt'] if account else '0'*32
    rounds=account['password_rounds'] if account else _PASSWORD_ROUNDS
    hashed=_password_digest(payload.password,salt,rounds)
    if not account or not hmac.compare_digest(hashed,account['password_hash']):
        raise HTTPException(401,'Invalid student roll number or password')
    with _student_auth_lock:
        _student_attempts[addr].clear()
        sid=secrets.token_urlsafe(32)
        csrf=secrets.token_urlsafe(32)
        _student_sessions[sid]={'student_id':account['id'],'csrf':csrf,'expires':time.time()+_STUDENT_SESSION_AGE}
    response.set_cookie('blockattend_student_sid',sid,httponly=True,samesite='strict',
                        secure=(env('COOKIE_SECURE')=='true' or request.url.scheme=='https'),
                        max_age=_STUDENT_SESSION_AGE,path='/')
    return {'authenticated':True,'csrf':csrf,'student':{
        'name':account['name'],'roll':account['roll'],
        'biometric_enrolled':bool(account['biometric_enrolled'])}}

@app.get('/api/student/status')
def student_status(request: Request):
    session=_student_session(request)
    if not session:return {'authenticated':False}
    student=db.get_student_login_by_id(session['student_id'])
    return {'authenticated':True,'csrf':session['csrf'],'student':{
        'name':student['name'],'roll':student['roll'],
        'biometric_enrolled':bool(student['biometric_enrolled'])}}

@app.post('/api/student/logout')
def student_logout(request: Request,response: Response,student=Depends(student_auth)):
    with _student_auth_lock:
        _student_sessions.pop(request.cookies.get('blockattend_student_sid',''),None)
    response.delete_cookie('blockattend_student_sid',path='/')
    return {'ok':True}

@app.post('/api/student/change-password')
def student_change_password(payload: StudentChangePassword,request: Request,
                            response: Response,student=Depends(student_auth)):
    account=db.student_login_record(db.get_student_login_by_id(student['student_id'])['roll'])
    current=_password_digest(payload.current_password,account['password_salt'],account['password_rounds'])
    if not hmac.compare_digest(current,account['password_hash']):
        raise HTTPException(401,'Current student password is incorrect')
    if hmac.compare_digest(payload.current_password,payload.new_password):
        raise HTTPException(400,'Choose a different password')
    salt=secrets.token_hex(16)
    if not db.put_student_login(student['student_id'],salt,_password_digest(payload.new_password,salt),_PASSWORD_ROUNDS):
        raise HTTPException(404,'Student account not found')
    with _student_auth_lock:
        for sid,value in list(_student_sessions.items()):
            if value['student_id']==student['student_id']:
                _student_sessions.pop(sid,None)
    response.delete_cookie('blockattend_student_sid',path='/')
    return {'ok':True,'relogin_required':True}

@app.post('/api/join/lookup')
def student_lookup(payload: StudentJoinLookup, request: Request, student=Depends(student_auth)):
    _limit_student_join(request,40)
    course=_class_from_join_code(payload.code)
    if not course:raise HTTPException(404,'Invalid class code. Ask your teacher for a valid code.')
    return {'title':course['title'],'course':course['course'],'open':not bool(course['closed_at'])}

@app.post('/api/join/attend')
def student_attend(payload: StudentJoinAttendance,request: Request,student=Depends(student_auth)):
    _limit_student_join(request,25)
    course=_class_from_join_code(payload.code)
    if not course or course['closed_at']:
        raise HTTPException(400,'Class not available or already closed.')
    claimed=db.get_student_login_by_id(student['student_id'])
    if not claimed or not claimed['biometric_enrolled']:
        raise HTTPException(400,'Your account has no enrolled face template. Ask faculty for help.')
    try:
        marked=service.mark_attendance(course['id'],payload.photo,expected_student_id=student['student_id'])
    except (service.BadRequest,ValueError):
        raise HTTPException(400,'Face verification failed or was uncertain. Ask faculty for review.')
    except LedgerError as exc:
        raise HTTPException(409,str(exc))
    return {'marked':True,'student':{'name':claimed['name'],'roll':claimed['roll']},
            'session':course['title'],'block_number':marked['receipt']['block_number'],
            'tx_hash':marked['receipt']['tx_hash'],'method':'FACE_MATCH',
            'note':'Academic prototype: face liveness is not verified.'}

@app.get('/api/auth/status')
def auth_status(request: Request):
    session = _auth_from_cookie(request)
    return {'authenticated': bool(session), 'csrf': session['csrf'] if session else None}

@app.post('/api/auth/login')
def login(payload: LoginRequest, request: Request, response: Response):
    addr = request.client.host if request.client else 'unknown'
    with _auth_lock:
        attempts = _failed[addr]
        now = time.time()
        while attempts and attempts[0] < now - 600:
            attempts.popleft()
        if len(attempts) >= 8:
            raise HTTPException(429, 'Too many attempts. Try again in 10 minutes.')
        # Constant-time compare to reduce simple timing leaks.
        expected = require_secret('ADMIN_PASSWORD')
        if not hmac.compare_digest(hashlib.sha256(payload.password.encode()).digest(),
                                   hashlib.sha256(expected.encode()).digest()):
            attempts.append(now)
            raise HTTPException(401, 'Incorrect faculty password')
        attempts.clear()
        sid = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        _sessions[sid] = {'csrf': csrf, 'expires': now + SESSION_AGE}
    response.set_cookie('blockattend_sid', sid, httponly=True, samesite='strict', secure=env('COOKIE_SECURE')=='true', max_age=SESSION_AGE, path='/')
    return {'authenticated': True, 'csrf': csrf}

@app.post('/api/auth/logout')
def logout(request: Request, response: Response, session=Depends(auth)):
    with _auth_lock:
        _sessions.pop(request.cookies.get('blockattend_sid',''), None)
    response.delete_cookie('blockattend_sid', path='/')
    return {'ok': True}

@app.get('/api/overview')
def overview(session=Depends(auth)):
    return service.overview()

@app.get('/api/students')
def students(session=Depends(auth)):
    return db.get_students()

@app.post('/api/students')
def enrol(payload: Enrollment, session=Depends(auth)):
    return service.enrol(payload.name, payload.roll, payload.photos, payload.consent)

@app.post('/api/students/manual')
def enrol_manual(payload: ManualStudentNew, session=Depends(auth)):
    return service.enrol_without_biometrics(payload.name, payload.roll)

@app.post('/api/students/{student_id}/credentials')
def provision_student_credentials(student_id: str,faculty=Depends(auth)):
    temporary_password=secrets.token_urlsafe(20)
    salt=secrets.token_hex(16)
    hashed=_password_digest(temporary_password,salt)
    if not db.put_student_login(student_id,salt,hashed,_PASSWORD_ROUNDS):
        raise HTTPException(404,'Student not found')
    with _student_auth_lock:
        for sid,value in list(_student_sessions.items()):
            if value['student_id']==student_id:
                _student_sessions.pop(sid,None)
    st=db.get_student_login_by_id(student_id)
    return {'roll':st['roll'],'temporary_password':temporary_password,
            'message':'Show the password privately to this student only. It cannot be recovered later.'}

@app.delete('/api/students/{student_id}')
def delete_student(student_id: str, session=Depends(auth)):
    return service.remove_student(student_id)

@app.get('/api/sessions')
def sessions(session=Depends(auth)):
    return [{**row, 'join_code': _class_join_code(row['id'])} for row in db.get_sessions()]

@app.get('/api/sessions/{session_id}/roster')
def session_roster(session_id: str, faculty=Depends(auth)):
    """Faculty-only ledger-derived attendance register for one class.

    No student images or biometric descriptors are returned. A flagged mark is
    not counted as present, and a learner is not presumed absent until the
    teacher closes the class.
    """
    target = next((s for s in db.get_sessions() if s['id'] == session_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail='Class session was not found')
    marks = service.attendance_report(session_id)
    records_by_student = {row['student_id']: row for row in reversed(marks) if row.get('student_id')}
    students = db.get_students()
    roster = []
    for student in students:
        record = records_by_student.get(student['id'])
        if record and record['status'] == 'Present':
            status = 'present'
        elif record:
            status = 'flagged'
        else:
            status = 'not_marked' if target['closed_at'] else 'pending'
        roster.append({
            'id': student['id'], 'name': student['name'], 'roll': student['roll'],
            'biometric_enrolled': student['templates'] > 0,
            'status': status,
            'method': record['method'] if record else None,
            'block_number': record['block_number'] if record else None,
            'tx_hash': record['tx_hash'] if record else None,
            'timestamp': record['timestamp'] if record else None
        })
    present = sum(row['status'] == 'present' for row in roster)
    return {'session': target, 'students': roster, 'total': len(roster),
            'present': present, 'remaining': len(roster) - present,
            'coverage_percent': round(present * 100 / len(roster)) if roster else 0}

@app.post('/api/sessions')
def create_session(payload: SessionNew, session=Depends(auth)):
    created = service.create_session(payload.title, payload.course)
    return {**created, 'join_code': _class_join_code(created['id'])}

@app.post('/api/sessions/{session_id}/close')
def close_session(session_id: str, session=Depends(auth)):
    return service.close_session(session_id)

@app.post('/api/recognize')
def recognize(payload: ImageScan, session=Depends(auth)):
    return service.recognize_student(payload.photo)

@app.post('/api/sessions/{session_id}/mark')
def mark_attendance(session_id: str, payload: ImageScan, session=Depends(auth)):
    return service.mark_attendance(session_id, payload.photo)

@app.post('/api/sessions/{session_id}/manual')
def faculty_override(session_id: str, payload: Correction, session=Depends(auth)):
    return service.manual_attendance(session_id, payload.student_id, payload.reason)

@app.post('/api/sessions/{session_id}/flag')
def flag_attendance(session_id: str, payload: Correction, session=Depends(auth)):
    return service.flag_attendance(session_id, payload.student_id, payload.reason)

@app.get('/api/attendance')
def attendance(session_id: str | None = None, session=Depends(auth)):
    return service.attendance_report(session_id)

@app.get('/api/ledger')
def ledger(session=Depends(auth)):
    return service.chain_explorer()

@app.get('/api/ledger/verify')
def verify(session=Depends(auth)):
    return service.get_ledger().verify()

@app.get('/api/attendance.csv')
def export_attendance(session_id: str | None = None, session=Depends(auth)):
    output = io.StringIO()
    writer = csv.writer(output)
    keys = ['session','course','student','roll','timestamp','method','status','block_number','tx_hash']
    writer.writerow(keys)
    for row in service.attendance_report(session_id):
        cells = []
        for col in keys:
            value = str(row.get(col) or '')
            if value.startswith(('=', '+', '-', '@', '\t', '\r')):
                value = "'" + value  # Prevent spreadsheet formula injection.
            cells.append(value)
        writer.writerow(cells)
    result = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    return StreamingResponse(result, media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="attendance-report.csv"'})
