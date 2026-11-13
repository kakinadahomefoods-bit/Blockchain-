import numpy as np
from fastapi.testclient import TestClient
from app.main import app, _join_attempts
from app import service

def test_student_self_service_join(monkeypatch):
    _join_attempts.clear()
    monkeypatch.setattr(service, 'describe_photo', lambda photo: np.ones(16*59,dtype=np.float32))
    with TestClient(app) as faculty:
        assert faculty.get('/join').status_code==200
        assert faculty.get('/static/student-join.js').status_code==200
        assert faculty.post('/api/join/lookup',json={'code':'000000000000'}).status_code==404
        login=faculty.post('/api/auth/login',json={'password':'correct-strong-password'})
        assert login.status_code==200
        faculty.headers['X-CSRF-Token']=login.json()['csrf']
        student=faculty.post('/api/students',json={'name':'Fictional Learner','roll':'CSE001','consent':True,'photos':['one','two','three']})
        assert student.status_code==200,student.text
        session=faculty.post('/api/sessions',json={'title':'Lab Session','course':'CSE101'})
        assert session.status_code==200,session.text
        sid=session.json()['id'];code=session.json()['join_code']
        assert len(code)==12
        assert faculty.get('/api/sessions').json()[0]['join_code']==code
        with TestClient(app) as learner:
            found=learner.post('/api/join/lookup',json={'code':code})
            assert found.status_code==200 and found.json()['open']
            invalid=learner.post('/api/join/attend',json={'code':code,'roll':'WRONG','photo':'fakeimage'*20})
            assert invalid.status_code==400 and 'Fictional Learner' not in invalid.text
            marked=learner.post('/api/join/attend',json={'code':code,'roll':'CSE001','photo':'fakeimage'*20})
            assert marked.status_code==200,marked.text
            assert marked.json()['method']=='FACE_MATCH'
            assert marked.json()['tx_hash']
            assert faculty.get('/api/sessions/'+sid+'/roster').json()['present']==1
            assert learner.post('/api/join/attend',json={'code':code,'roll':'CSE001','photo':'fakeimage'*20}).status_code==409
            assert faculty.post('/api/sessions/'+sid+'/close').status_code==200
            assert learner.post('/api/join/attend',json={'code':code,'roll':'CSE001','photo':'fakeimage'*20}).status_code==400
            assert faculty.get('/api/ledger/verify').json()['valid']
