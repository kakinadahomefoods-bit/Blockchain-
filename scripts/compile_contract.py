"""Compile Solidity using project's locally installed solcjs."""
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / 'node_modules' / '.bin' / ('solcjs.cmd' if sys.platform == 'win32' else 'solcjs')
if not BIN.exists():
    sys.exit('Missing solcjs. First run: npm install')
build = ROOT / 'build'
build.mkdir(exist_ok=True)
cmd = [str(BIN), '--bin', '--abi', '--optimize', '-o', str(build),
       str(ROOT / 'contracts' / 'AttendanceLedger.sol')]
if sys.platform == 'win32':
    cmd = ['cmd', '/c'] + cmd
subprocess.run(cmd, check=True, cwd=str(ROOT))
files = list(build.glob('*AttendanceLedger.abi'))
if len(files) != 1:
    sys.exit(f'Expected exactly one AttendanceLedger ABI, found {len(files)}')
abi = json.loads(files[0].read_text())
bytecode = files[0].with_suffix('.bin').read_text().strip()
artifact = {'contractName': 'AttendanceLedger', 'abi': abi, 'bytecode': '0x' + bytecode}
(build / 'contract.json').write_text(json.dumps(artifact, indent=2))
print('Compiled contract to build/contract.json')
