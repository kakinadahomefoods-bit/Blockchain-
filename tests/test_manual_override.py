"""Tests honest faculty override, ledger rules, and tamper diagnostics."""
import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import service
from app.ledger import LocalLedger, LedgerError, token


def test_manual_override_cannot_mask_biometric_or_duplicate():
    chain = LocalLedger()
    ses, stu = token('session', 'demo-lab'), token('student', 'student-01')
    chain.create_session(ses)
    receipt = chain.manual_attendance(ses, stu, 'Camera not working; teacher checked identity')
    assert receipt['tx_hash']
    manual = chain.events()[-1]
    assert manual['type'] == 'manual'
    assert 'reason' not in manual
    assert len(manual['reason_hash']) == 64
    with pytest.raises(LedgerError, match='Duplicate'):
        chain.mark_attendance(ses, stu)
    chain.void_attendance(ses, stu, 'Student marked by mistake')
    assert chain.verify()['valid'] is True


def test_faculty_override_api_and_status(monkeypatch):
    monkeypatch.setattr(service, 'describe_photo', lambda img: np.ones(16*59, dtype=np.float32))
    with TestClient(app) as client:
        assert client.get('/health').json()['status'] == 'ok'
        login = client.post('/api/auth/login', json={'password': 'correct-strong-password'})
        csrf = login.json()['csrf']
        client.headers.update({'X-CSRF-Token': csrf})
        reg = client.post('/api/students', json={
            'name': 'Volunteer A', 'roll': '2026CSE101', 'consent': True,
            'photos': ['image1', 'image2', 'image3']
        })
        assert reg.status_code == 200
        sid = reg.json()['id']
        session = client.post('/api/sessions', json={'title': 'Blockchain Systems', 'course': 'FBT'})
        assert session.status_code == 200
        session_id = session.json()['id']
        bad = client.post(f'/api/sessions/{session_id}/manual', json={'student_id': sid, 'reason': 'oops'})
        assert bad.status_code == 400
        mark = client.post(f'/api/sessions/{session_id}/manual', json={
            'student_id': sid, 'reason': 'Webcam unavailable; faculty verifies ID'
        })
        assert mark.status_code == 200
        assert mark.json()['method'] == 'manual'
        report = client.get('/api/attendance').json()
        assert len(report) == 1
        assert report[0]['method'] == 'Faculty override'
        assert client.post(f'/api/sessions/{session_id}/mark', json={'photo': 'example'}).status_code == 409
        ledger = client.get('/api/ledger').json()
        assert ledger['events'][0]['type'] == 'manual'
        assert ledger['verification']['valid']
        assert 'Faculty override' in client.get('/api/attendance.csv').text
        assert client.post(f'/api/sessions/{session_id}/flag', json={
            'student_id': sid, 'reason': 'Mistaken student'}).status_code == 200
        assert client.get('/api/attendance').json()[0]['status'] == 'Flagged / correction'


def test_tamper_view_reports_invalid_chain():
    chain = LocalLedger()
    chain.create_session(token('session', 'demo'))
    row = json.loads(chain.path.read_text().splitlines()[0])
    row['payload']['session_token'] = '0' * 64
    chain.path.write_text(json.dumps(row) + '\n')
    with TestClient(app) as client:
        assert client.post('/api/auth/login', json={'password': 'correct-strong-password'}).status_code == 200
        verification = client.get('/api/ledger/verify').json()
        assert verification['valid'] is False
        explorer = client.get('/api/ledger').json()
        assert explorer['verification']['valid'] is False
        assert explorer['events'] == []


def test_manual_only_registration_without_camera():
    with TestClient(app) as client:
        login=client.post('/api/auth/login',json={'password':'correct-strong-password'})
        client.headers.update({'X-CSRF-Token':login.json()['csrf']})
        response=client.post('/api/students/manual',json={'name':'Student No Camera','roll':'2026CSE102'})
        assert response.status_code==200
        student=response.json()
        assert student['templates']==0
        assert client.get('/api/students').json()[0]['templates']==0
        session=client.post('/api/sessions',json={'title':'Lab without camera','course':'FBT'}).json()
        marked=client.post(f"/api/sessions/{session['id']}/manual",json={'student_id':student['id'],'reason':'Camera hardware failed in the lab'})
        assert marked.status_code==200
        assert client.get('/api/attendance').json()[0]['method']=='Faculty override'
