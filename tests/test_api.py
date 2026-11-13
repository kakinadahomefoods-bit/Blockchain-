import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app import service


def test_end_to_end_api_flow(monkeypatch):
    # Stub ONLY the camera recognition for this API test; blockchain writes and
    # authorization are real and separately tested. Real Haar detection needs
    # real consented webcam images, tested manually on user hardware.
    monkeypatch.setattr(service, 'describe_photo', lambda photo: np.ones(16*59,dtype=np.float32))
    with TestClient(app) as client:
        assert client.get('/').status_code == 200
        assert client.get('/api/students').status_code == 401
        assert client.get('/api/sessions/unknown/roster').status_code == 401
        assert client.post('/api/auth/login',json={'password':'wrong'}).status_code == 401
        login=client.post('/api/auth/login',json={'password':'correct-strong-password'})
        assert login.status_code==200
        csrf=login.json()['csrf']
        assert client.post('/api/sessions',json={'title':'Demo Class','course':'CSE'}).status_code == 403
        client.headers.update({'X-CSRF-Token':csrf})
        reg=client.post('/api/students',json={'name':'Student Example','roll':'CSE001','consent':True,
                                               'photos':['photo 1','photo 2','photo 3']})
        assert reg.status_code==200,reg.text
        student=reg.json()
        denied=client.post('/api/students',json={'name':'Other Student','roll':'CSE002','consent':False,'photos':['1','2','3']})
        assert denied.status_code==400
        session=client.post('/api/sessions',json={'title':'Blockchain Lab','course':'FBT101'})
        assert session.status_code==200,session.text
        session_id=session.json()['id']
        roster=client.get(f'/api/sessions/{session_id}/roster')
        assert roster.status_code==200 and roster.json()['present']==0
        assert roster.json()['students'][0]['status']=='pending'
        assert client.get('/api/sessions/unknown/roster').status_code==404
        scan=client.post('/api/recognize',json={'photo':'photo 4'})
        assert scan.json()['recognized'] is True
        mark=client.post(f'/api/sessions/{session_id}/mark',json={'photo':'photo 5'})
        assert mark.status_code==200,mark.text
        assert mark.json()['receipt']['tx_hash']
        roster=client.get(f'/api/sessions/{session_id}/roster').json()
        assert roster['present']==1 and roster['coverage_percent']==100
        assert roster['students'][0]['method']=='Face scan'
        assert roster['students'][0]['tx_hash']
        duplicate=client.post(f'/api/sessions/{session_id}/mark',json={'photo':'photo 6'})
        assert duplicate.status_code==409
        report=client.get('/api/attendance')
        assert len(report.json())==1
        assert report.json()[0]['student']=='Student Example'
        csv=client.get('/api/attendance.csv')
        assert csv.status_code==200 and 'Student Example' in csv.text
        flag=client.post(f'/api/sessions/{session_id}/flag',json={'student_id':student['id'],
                                                                  'reason':'Testing correction'})
        assert flag.status_code==200,flag.text
        assert client.get('/api/attendance').json()[0]['status']=='Flagged / correction'
        assert client.get(f'/api/sessions/{session_id}/roster').json()['students'][0]['status']=='flagged'
        close=client.post(f'/api/sessions/{session_id}/close')
        assert close.status_code==200,close.text
        assert client.get('/api/ledger/verify').json()['valid'] is True
        assert len(client.get('/api/ledger').json()['events'])==4
        assert client.post(f'/api/sessions/{session_id}/mark',json={'photo':'again'}).status_code==400
        deletion=client.delete('/api/students/'+student['id'])
        assert deletion.status_code==200
        assert len(client.get('/api/students').json())==0
        assert client.get('/api/attendance').json()[0]['student']=='[Deleted student]'
        assert client.post('/api/auth/logout').status_code==200
        assert client.get('/api/students').status_code==401
