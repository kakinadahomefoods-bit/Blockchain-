"""Run the local classroom server: python app.py"""
import sys
from app.config import env, require_secret
if __name__ == '__main__':
    try:
        require_secret('ADMIN_PASSWORD')
        require_secret('HMAC_KEY')
    except RuntimeError as e:
        sys.exit(str(e))
    import uvicorn
    # Bind to localhost by default. Camera API is allowed on secure origins/localhost.
    uvicorn.run('app.main:app', host='127.0.0.1', port=int(env('PORT','8000')), reload=False)
