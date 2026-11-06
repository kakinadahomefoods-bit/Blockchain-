"""Project configuration. No fixed passwords, tokens or personal data are committed."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'

def load_env(path=ROOT / '.env'):
    if path.exists():
        for row in path.read_text(encoding='utf8').splitlines():
            row = row.strip()
            if not row or row.startswith('#') or '=' not in row:
                continue
            key, val = row.split('=', 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

load_env()

def env(name, default=''):
    return os.environ.get(name, default)

def data_dir():
    p = Path(env('DATA_DIR', str(DATA))).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p

def require_secret(name):
    value = env(name)
    if not value or value.startswith('REPLACE_'):
        raise RuntimeError(f'Missing {name}. First run: python scripts/init_project.py')
    return value
