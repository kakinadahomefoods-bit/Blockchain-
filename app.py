"""Entry point for Vercel and the original local classroom application.

Vercel imports the ASGI variable `app`; `python app.py` keeps launching the
complete local server without pretending its SQLite/Ganache state is cloud-safe.
"""
from cloud_entry import app

if __name__ == '__main__':
    import sys
    from app.config import env, require_secret
    try:
        require_secret('ADMIN_PASSWORD')
        require_secret('HMAC_KEY')
    except RuntimeError as exc:
        sys.exit(str(exc))
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=int(env('PORT', '8000')), reload=False)
