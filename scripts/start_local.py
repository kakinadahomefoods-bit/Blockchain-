"""Single command: run the fully offline signed-ledger classroom demonstration."""
import os
import sys
import webbrowser
from pathlib import Path
from threading import Timer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.init_project import main as initialize


def main():
    initialize()
    # init_project creates .env after app.config was first imported; reload secrets.
    from app.config import load_env
    load_env()
    os.environ['CHAIN_BACKEND'] = 'local'
    os.environ['DATA_DIR'] = str(ROOT / 'data' / 'local')
    from app.db import initialize as init_db
    from app.ledger import init_signer
    init_db()
    init_signer()
    import uvicorn
    port = int(os.environ.get('PORT', '8000'))
    print('\nMODE: Signed single-node educational blockchain (no Ethereum consensus).')
    print(f'Browser: http://127.0.0.1:{port}')
    Timer(2, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
    uvicorn.run('app.main:app', host='127.0.0.1', port=port, log_level='warning')


if __name__ == '__main__':
    main()
