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
    if filename not in ('app.js','styles.css','logo.svg'):
        raise HTTPException(404)
    return FileResponse(ROOT / 'static' / filename)

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

@app.delete('/api/students/{student_id}')
def delete_student(student_id: str, session=Depends(auth)):
    return service.remove_student(student_id)

@app.get('/api/sessions')
def sessions(session=Depends(auth)):
    return db.get_sessions()

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
    return service.create_session(payload.title, payload.course)

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
