"""Authenticated student login, class join, face verification and real local ledger writes."""
import numpy as np
from fastapi.testclient import TestClient
from app.main import app, _join_attempts, _student_attempts, _student_sessions
from app import service, db

def signin(client, roll, password):
    r=client.post('/api/student/login',json={'roll':roll,'password':password})
    assert r.status_code==200,r.text
    client.headers['X-CSRF-Token']=r.json()['csrf']
    return r.json()

def test_faculty_creates_student_login_then_face_verified_attendance(monkeypatch):
    _join_attempts.clear();_student_attempts.clear();_student_sessions.clear()
    monkeypatch.setattr(service,'describe_photo',lambda image:np.ones(16*59,dtype=np.float32))
    with TestClient(app) as faculty:
        assert faculty.get('/join').status_code==200
        assert faculty.post('/api/join/lookup',json={'code':'000000000000'}).status_code==401
        assert faculty.post('/api/join/attend',json={'code':'000000000000','photo':'x'*150}).status_code==401
        assert faculty.post('/api/students/fake/credentials').status_code==401
        login=faculty.post('/api/auth/login',json={'password':'correct-strong-password'})
        assert login.status_code==200
        faculty.headers['X-CSRF-Token']=login.json()['csrf']
        student=faculty.post('/api/students',json={'name':'Fictional Learner','roll':'CSE001','consent':True,'photos':['one','two','three']})
        assert student.status_code==200,student.text
        secret=faculty.post('/api/students/'+student.json()['id']+'/credentials')
        assert secret.status_code==200,secret.text
        password=secret.json()['temporary_password']
        assert password not in str(db.student_login_record('CSE001'))
        assert faculty.get('/api/students').json()[0]['login_enabled']==1
        session=faculty.post('/api/sessions',json={'title':'Lab Session','course':'CSE101'})
        assert session.status_code==200,session.text
        sid=session.json()['id'];code=session.json()['join_code']
        assert len(code)==12
        with TestClient(app) as learner:
            assert learner.post('/api/student/login',json={'roll':'CSE001','password':'wrong'}).status_code==401
            signin(learner,'CSE001',password)
            assert learner.get('/api/student/status').json()['student']['roll']=='CSE001'
            assert learner.get('/api/sessions').status_code==401
            valid_csrf=learner.headers.pop('X-CSRF-Token')
            assert learner.post('/api/join/lookup',json={'code':code}).status_code==403
            learner.headers['X-CSRF-Token']=valid_csrf
            found=learner.post('/api/join/lookup',json={'code':code})
            assert found.status_code==200 and found.json()['open']
            marked=learner.post('/api/join/attend',json={'code':code,'photo':'faceimage'*20})
            assert marked.status_code==200,marked.text
            assert marked.json()['method']=='FACE_MATCH'
            assert marked.json()['tx_hash']
            assert faculty.get('/api/sessions/'+sid+'/roster').json()['present']==1
            assert learner.post('/api/join/attend',json={'code':code,'photo':'faceimage'*20}).status_code==409
            assert faculty.get('/api/ledger/verify').json()['valid']
            assert learner.post('/api/student/logout',json={}).status_code==200
            assert learner.post('/api/join/attend',json={'code':code,'photo':'faceimage'*20}).status_code==401
        assert faculty.post('/api/sessions/'+sid+'/close').status_code==200

def test_student_password_change_and_reset_revoke_sessions():
    _student_sessions.clear();_student_attempts.clear()
    with TestClient(app) as faculty:
        result=faculty.post('/api/auth/login',json={'password':'correct-strong-password'})
        faculty.headers['X-CSRF-Token']=result.json()['csrf']
        user=faculty.post('/api/students/manual',json={'name':'Sample Student','roll':'CSE222'})
        assert user.status_code==200
        sid=user.json()['id']
        creds=faculty.post('/api/students/'+sid+'/credentials').json()
        with TestClient(app) as student:
            signin(student,'CSE222',creds['temporary_password'])
            assert not student.get('/api/student/status').json()['student']['biometric_enrolled']
            wrong=student.post('/api/student/change-password',json={'current_password':'bad','new_password':'a-good-new-password'})
            assert wrong.status_code==401
            change=student.post('/api/student/change-password',json={'current_password':creds['temporary_password'],'new_password':'a-good-new-password'})
            assert change.status_code==200
            assert student.get('/api/student/status').json()['authenticated'] is False
            assert student.post('/api/student/login',json={'roll':'CSE222','password':creds['temporary_password']}).status_code==401
            signin(student,'CSE222','a-good-new-password')
            newer=faculty.post('/api/students/'+sid+'/credentials')
            assert newer.status_code==200
            assert student.get('/api/student/status').json()['authenticated'] is False
            signin(student,'CSE222',newer.json()['temporary_password'])
            assert faculty.delete('/api/students/'+sid).status_code==200
            assert student.get('/api/student/status').json()['authenticated'] is False

def test_signed_in_account_must_match_face(monkeypatch):
    _student_sessions.clear();_student_attempts.clear()
    monkeypatch.setattr(service,'describe_photo',lambda photo:np.ones(16*59,dtype=np.float32))
    with TestClient(app) as faculty:
        logged=faculty.post('/api/auth/login',json={'password':'correct-strong-password'})
        faculty.headers['X-CSRF-Token']=logged.json()['csrf']
        a=faculty.post('/api/students',json={'name':'Identity A','roll':'CSEA11','consent':True,'photos':['a','b','c']})
        b=faculty.post('/api/students',json={'name':'Identity B','roll':'CSEB11','consent':True,'photos':['d','e','f']})
        assert a.status_code==200 and b.status_code==200
        credentials=faculty.post('/api/students/'+b.json()['id']+'/credentials').json()
        klass=faculty.post('/api/sessions',json={'title':'Security Lab','course':'CSE401'}).json()
        monkeypatch.setattr(service,'recognize_student',lambda _: {'recognized':True,'student':{'id':a.json()['id'],'name':'Identity A','roll':'CSEA11'},'distance':0.01})
        with TestClient(app) as learner:
            signin(learner,'CSEB11',credentials['temporary_password'])
            mismatch=learner.post('/api/join/attend',json={'code':klass['join_code'],'photo':'sample-photo'*20})
            assert mismatch.status_code==400
            assert faculty.get('/api/sessions/'+klass['id']+'/roster').json()['present']==0
