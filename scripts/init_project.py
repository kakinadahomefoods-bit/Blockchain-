"""First-run wizard: creates unique faculty password + secret; no shared defaults."""
import secrets
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.ledger import init_signer
from app.config import DATA
from app import db

def main():
    envfile = ROOT / '.env'
    if envfile.exists():
        print('A .env already exists. To avoid wiping project secrets, it was NOT replaced.')
        print('Use your existing ADMIN_PASSWORD or edit .env while app is stopped.')
    else:
        password = secrets.token_urlsafe(12)
        envfile.write_text('ADMIN_PASSWORD=' + password + '\nHMAC_KEY=' + secrets.token_hex(32) +
                           '\nCHAIN_BACKEND=local\nPORT=8000\nFACE_DISTANCE_THRESHOLD=0.30\nFACE_DISTANCE_MARGIN=0.035\n', encoding='utf8')
        try:
            envfile.chmod(0o600)
        except OSError:
            pass
        print('\n================ FACULTY LOGIN ================')
        print('Password:', password)
        print('Save this password privately; it will not be displayed again.')
        print('================================================\n')
        DATA.mkdir(parents=True, exist_ok=True)
        login_file = DATA / 'login-info.txt'
        login_file.write_text('BlockAttend faculty password (private): ' + password + '\n'
                              'Generated locally. Never share this file.\n', encoding='utf8')
        try:
            login_file.chmod(0o600)
        except OSError:
            pass
        print('You can find it in data/login-info.txt on this computer.')
    DATA.mkdir(exist_ok=True)
    db.initialize()
    init_signer()
    print('Local blockchain and student database initialized.')
    print('Next: python app.py   then open http://127.0.0.1:8000')

if __name__ == '__main__':
    main()
