"""One-click local Ethereum dev-chain orchestrator. Never opens RPC on the LAN.

Requires Python libraries + Node/npm packages installed by windows_one_click.ps1.
The Ganache database, faculty database and contract survive clean restarts.
"""
import atexit
import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from threading import Timer
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RPC = 'http://127.0.0.1:8545'


def rpc(method, params=None):
    payload = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or []}).encode()
    with urlopen(Request(RPC, data=payload, headers={'Content-Type': 'application/json'}), timeout=2) as response:
        body = json.loads(response.read())
    if 'error' in body:
        raise RuntimeError(body['error'])
    return body['result']


def connected():
    try:
        return int(rpc('eth_chainId'), 16) == 1337
    except Exception:
        return False


def run_python(script):
    subprocess.run([sys.executable, str(ROOT / 'scripts' / script)], cwd=ROOT, check=True)


def main():
    from scripts.init_project import main as initialize
    initialize()
    # init_project creates .env after app.config was first imported; reload secrets.
    from app.config import load_env
    load_env()
    os.environ['CHAIN_BACKEND'] = 'ethereum'
    os.environ['DATA_DIR'] = str(ROOT / 'data' / 'evm')
    from app.db import initialize as initialize_db
    initialize_db()
    from app.config import env

    try:
        from web3 import Web3
    except ImportError as exc:
        raise RuntimeError('Web3 Python package missing: pip install -r requirements-ethereum.txt') from exc

    cli = ROOT / 'node_modules' / 'ganache' / 'dist' / 'node' / 'cli.js'
    if not cli.exists():
        raise RuntimeError('Ganache missing: npm install (inside this project folder)')
    node_bin = os.environ.get('BLOCKATTEND_NODE_EXE', 'node')
    ganache_process = None
    loghandle = None
    if not connected():
        (ROOT / 'data' / 'evm').mkdir(parents=True, exist_ok=True)
        logfile = ROOT / 'data' / 'evm' / 'ganache.log'
        loghandle = logfile.open('a', encoding='utf8')
        args = [node_bin, str(cli), '--wallet.deterministic', '--chain.chainId', '1337',
                '--server.host', '127.0.0.1', '--server.port', '8545',
                '--database.dbPath', str(ROOT / 'data' / 'evm' / 'ganache_db'),
                '--logging.quiet']
        print('Starting local Ganache blockchain at 127.0.0.1:8545...')
        ganache_process = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL,
                                           stdout=loghandle, stderr=subprocess.STDOUT)
        # Also clean up if a startup exception occurs before the main try/finally.
        atexit.register(lambda process=ganache_process: process.poll() is None and process.terminate())
        for i in range(60):
            if connected():
                break
            if ganache_process.poll() is not None:
                raise RuntimeError(f'Ganache exited. Check {logfile}')
            time.sleep(.5)
        if not connected():
            raise RuntimeError(f'Ganache failed to start. See {logfile}')
    else:
        print('Reusing a local Ethereum node on port 8545 (chain ID 1337).')

    try:
        if int(rpc('eth_chainId'), 16) != 1337:
            raise RuntimeError('RPC port 8545 is occupied by a different blockchain; stop it first')

        artifact = ROOT / 'build' / 'contract.json'
        if not artifact.exists():
            print('Compiling Solidity attendance contract...')
            run_python('compile_contract.py')
        w3 = Web3(Web3.HTTPProvider(RPC))
        address = env('CONTRACT_ADDRESS')
        has_code = bool(address and w3.eth.get_code(w3.to_checksum_address(address)))
        if not has_code:
            # After Ethereum node data loss, never redeploy quietly while
            # attendance metadata still references old, now-missing events.
            from app.db import connect
            with connect() as conn:
                stored = conn.execute('SELECT COUNT(*) FROM class_sessions').fetchone()[0]
            if stored:
                raise RuntimeError('The previous smart contract is missing but old sessions exist. '
                                   'Restore your data/evm/ganache_db backup; no automatic reset performed.')
            print('Deploying Solidity smart contract to Ganache...')
            run_python('deploy_contract.py')
        else:
            print('Using previously deployed attendance smart contract:', address)
        os.environ['CHAIN_BACKEND'] = 'ethereum'
        # Deployment updates .env on disk. Force the current process to see it.
        if not has_code:
            for line in (ROOT / '.env').read_text().splitlines():
                if line.startswith('CONTRACT_ADDRESS='):
                    os.environ['CONTRACT_ADDRESS'] = line.split('=',1)[1].strip()
        from app.ledger import get_ledger
        ledger = get_ledger()
        assert ledger.verify()['valid'], 'Failed to verify EVM ledger'
        print('SOLIDITY MODE READY. Local Ethereum transactions are active.')
        import uvicorn
        port = int(os.environ.get('PORT', '8000'))
        Timer(2, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
        print(f'Attendance dashboard: http://127.0.0.1:{port}')
        uvicorn.run('app.main:app', host='127.0.0.1', port=port, log_level='warning')
    finally:
        if ganache_process is not None:
            ganache_process.terminate()
            try:
                ganache_process.wait(timeout=6)
            except subprocess.TimeoutExpired:
                ganache_process.kill()
        if loghandle:
            loghandle.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('EVM STARTUP ERROR:', exc, file=sys.stderr)
        sys.exit(1)
