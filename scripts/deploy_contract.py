"""Deploy contract to a local Ganache blockchain with unlocked test accounts."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import env
try:
    from web3 import Web3
except ImportError:
    sys.exit('Install Ethereum dependencies: pip install -r requirements-ethereum.txt')
w3 = Web3(Web3.HTTPProvider(env('RPC_URL','http://127.0.0.1:8545')))
if not w3.is_connected():
    sys.exit('Run npm run chain in another terminal first')
artifact = json.loads((ROOT / 'build' / 'contract.json').read_text())
wallet = w3.eth.accounts[0]
contract = w3.eth.contract(abi=artifact['abi'], bytecode=artifact['bytecode'])
tx = contract.constructor().transact({'from': wallet, 'gas': 2500000})
receipt = w3.eth.wait_for_transaction_receipt(tx, timeout=60)
if receipt.status != 1:
    sys.exit('Deployment failed')
address = receipt.contractAddress
path = ROOT / '.env'
contents = path.read_text() if path.exists() else ''
lines = [l for l in contents.splitlines() if not l.startswith(('CONTRACT_ADDRESS=', 'CHAIN_BACKEND='))]
lines += [f'CONTRACT_ADDRESS={address}', 'CHAIN_BACKEND=ethereum']
path.write_text('\n'.join(lines) + '\n')
print('Deployed to', address)
print('Enabled CHAIN_BACKEND=ethereum. Restart python app.py. Local Ganache only.')
