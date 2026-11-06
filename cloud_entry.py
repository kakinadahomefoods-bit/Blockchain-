"""Vercel-safe frontend preview; never runs local SQLite/OpenCV/Ganache.

This service intentionally blocks real student/biometric writes. A production
deployment requires authenticated persistent storage and an EVM RPC backend.
"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).resolve().parent
app = FastAPI(title='BlockAttend Hosted Preview', docs_url=None, redoc_url=None)

@app.middleware('http')
async def headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"
    return response

@app.get('/')
def index():
    return FileResponse(ROOT / 'cloud' / 'index.html', media_type='text/html')

@app.get('/health')
def health():
    return {'status': 'ok', 'mode': 'browser-only-demo',
            'persistent_server_storage': False,
            'face_recognition_connected': False,
            'ethereum_connected': False}

@app.api_route('/api/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def disabled_server_api(path: str):
    return JSONResponse(status_code=503, content={
        'detail': 'Hosted browser demo only. Real faculty authentication, face recognition, persistent records and Ethereum transactions require a separate secure backend.',
        'mode': 'browser-only-demo'
    })
