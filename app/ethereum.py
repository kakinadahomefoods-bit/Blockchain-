"""Real Ethereum-compatible local blockchain adapter (Ganache JSON-RPC).

Requires `pip install -r requirements-ethereum.txt`, npm install, npm run chain,
python scripts/compile_contract.py, python scripts/deploy_contract.py.
Uses an unlocked LOCAL Ganache account. NEVER expose RPC outside localhost.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from .config import ROOT, env
from .ledger import LedgerError

class EthereumLedger:
    backend = 'ethereum'

    def __init__(self):
        try:
            from web3 import Web3
        except ImportError as e:
            raise LedgerError('Ethereum mode requires: pip install -r requirements-ethereum.txt') from e
        self.w3 = Web3(Web3.HTTPProvider(env('RPC_URL', 'http://127.0.0.1:8545'), request_kwargs={'timeout': 10}))
        if not self.w3.is_connected():
            raise LedgerError('Cannot connect to local Ethereum node; run npm run chain')
        artifact_file = ROOT / 'build' / 'contract.json'
        address = env('CONTRACT_ADDRESS')
        if not artifact_file.exists() or not address:
            raise LedgerError('Missing compiled contract/deployment; run npm run compile and python scripts/deploy_contract.py')
        artifact = json.loads(artifact_file.read_text(encoding='utf8'))
        self.address = self.w3.to_checksum_address(address)
        if not self.w3.eth.get_code(self.address):
            raise LedgerError('Contract address does not contain bytecode on this chain; redeploy')
        self.contract = self.w3.eth.contract(address=self.address, abi=artifact['abi'])
        accounts = self.w3.eth.accounts
        if not accounts:
            raise LedgerError('Ganache has no unlocked accounts')
        self.wallet = accounts[0]
        if not self.contract.functions.faculty(self.wallet).call():
            raise LedgerError('Local wallet is not an authorized faculty account')

    def _tx(self, action):
        from web3.exceptions import ContractLogicError
        try:
            txid = action.transact({'from': self.wallet, 'gas': 250000})
            receipt = self.w3.eth.wait_for_transaction_receipt(txid, timeout=40)
            if receipt['status'] != 1:
                raise LedgerError('Transaction reverted; duplicate, closed session, or unauthorized writer')
            block = self.w3.eth.get_block(receipt['blockNumber'])
            return {'tx_hash': txid.hex(), 'block_number': receipt['blockNumber'],
                    'timestamp': datetime.fromtimestamp(block['timestamp'], timezone.utc).isoformat(timespec='seconds')}
        except LedgerError:
            raise
        except Exception as e:
            raise LedgerError(f'Ethereum transaction rejected: {str(e)[:200]}') from e

    @staticmethod
    def raw(token):
        return bytes.fromhex(token)

    def create_session(self, session_token):
        return self._tx(self.contract.functions.createSession(self.raw(session_token)))

    def close_session(self, session_token):
        return self._tx(self.contract.functions.closeSession(self.raw(session_token)))

    def mark_attendance(self, session_token, student_token):
        return self._tx(self.contract.functions.markAttendance(self.raw(session_token), self.raw(student_token)))

    def manual_attendance(self, session_token, student_token, reason):
        reason_hash = hashlib.sha256(reason.encode('utf8')).digest()
        return self._tx(self.contract.functions.manualMarkAttendance(
            self.raw(session_token), self.raw(student_token), reason_hash))

    def void_attendance(self, session_token, student_token, reason):
        reason_hash = hashlib.sha256(reason.encode('utf8')).digest()
        return self._tx(self.contract.functions.flagAttendance(self.raw(session_token), self.raw(student_token), reason_hash))

    def events(self):
        contract = self.contract
        kinds = [('SessionCreated', 'create'), ('SessionClosed', 'close'),
                 ('AttendanceMarked', 'mark'), ('ManualAttendanceMarked', 'manual'), ('AttendanceFlagged', 'void')]
        result = []
        for name, kind in kinds:
            for ev in getattr(contract.events, name)().get_logs(from_block=0):
                args = ev['args']
                block = self.w3.eth.get_block(ev['blockNumber'])
                result.append({
                    'type': kind, 'session_token': bytes(args['sessionId']).hex(),
                    'student_token': bytes(args['studentId']).hex() if 'studentId' in args else None,
                    'tx_hash': ev['transactionHash'].hex(), 'block_number': ev['blockNumber'],
                    'log_index': ev['logIndex'],
                    'timestamp': datetime.fromtimestamp(block['timestamp'], timezone.utc).isoformat(timespec='seconds')
                })
        return sorted(result, key=lambda x: (x['block_number'], x['log_index']))

    def verify(self):
        try:
            block = self.w3.eth.get_block('latest')
            events = self.events()
            return {'valid': True, 'checked': len(events), 'head': block['hash'].hex(),
                    'block_height': block['number'], 'backend': 'ethereum',
                    'note': 'Ethereum node confirms contract logs; security depends on network consensus and key safety'}
        except Exception as e:
            return {'valid': False, 'checked': 0, 'reason': str(e)[:160], 'backend': 'ethereum'}

    def blocks(self):
        return self.events()
