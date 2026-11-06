"""Independent command-line verification without the browser UI."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.ledger import get_ledger
result = get_ledger().verify()
print(json.dumps(result, indent=2))
sys.exit(0 if result['valid'] else 1)
