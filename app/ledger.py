"""Signed hash-linked local blockchain for offline demonstrations.

ED25519 signatures and hashes make edits detectable, but this single-node demo
is NOT decentralized and cannot resist a malicious node operator with its key.
For real EVM transactions select CHAIN_BACKEND=ethereum.
"""
import hashlib
import hmac
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from .config import data_dir, require_secret

_LOCK = threading.RLock()

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf8')

def digest(content):
    return hashlib.sha256(canonical(content)).hexdigest()

def token(kind, identifier):
    return hmac.new(bytes.fromhex(require_secret('HMAC_KEY')), f'{kind}:{identifier}'.encode(), hashlib.sha256).hexdigest()

def signer_path():
    return data_dir() / 'validator-key.pem'

def init_signer():
    if signer_path().exists():
        return
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    # Create exclusively. Never replace an existing key: old blocks require it.
    fd = os.open(str(signer_path()), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(pem)

def load_signer():
    init_signer()
    return serialization.load_pem_private_key(signer_path().read_bytes(), password=None)

class LedgerError(Exception):
    pass

class LocalLedger:
    backend = 'local'

    def __init__(self):
        self.path = data_dir() / 'chain.jsonl'
        self.key = load_signer()
        self.public_key = self.key.public_key()
        if not self.path.exists():
            self.path.touch(mode=0o600)

    def blocks(self):
        with _LOCK:
            try:
                with self.path.open(encoding='utf8') as f:
                    return [json.loads(line) for line in f if line.strip()]
            except (ValueError, OSError) as e:
                raise LedgerError(f'Cannot read blockchain: {e}') from e

    def verify(self):
        blocks = self.blocks()
        prev = '0' * 64
        public_raw = self.public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        for i, block in enumerate(blocks):
            payload = block.get('payload')
            if not isinstance(payload, dict) or block.get('index') != i + 1 or block.get('previous_hash') != prev:
                return {'valid': False, 'checked': i, 'reason': f'Broken link at block {i + 1}', 'backend': 'local'}
            unsigned = {k: block[k] for k in ('index','previous_hash','created_at','payload','public_key') if k in block}
            if block.get('public_key') != public_raw.hex() or digest(unsigned) != block.get('hash'):
                return {'valid': False, 'checked': i, 'reason': f'Invalid block hash at block {i + 1}', 'backend': 'local'}
            try:
                self.public_key.verify(bytes.fromhex(block['signature']), bytes.fromhex(block['hash']))
            except (ValueError, KeyError, Exception):
                return {'valid': False, 'checked': i, 'reason': f'Invalid signature at block {i + 1}', 'backend': 'local'}
            prev = block['hash']
        return {'valid': True, 'checked': len(blocks), 'head': prev, 'backend': 'local',
                'note': 'Signed single-node chain: tamper-evident, not decentralized'}

    def _append(self, kind, session, student=None, reason=None):
        with _LOCK:
            verified = self.verify()
            if not verified['valid']:
                raise LedgerError('Blockchain integrity check failed; refusing to append: ' + verified['reason'])
            events = self.events()
            if kind == 'create':
                if any(e['type']=='create' and e['session_token']==session for e in events):
                    raise LedgerError('This session already exists on-chain')
            else:
                if not any(e['type']=='create' and e['session_token']==session for e in events):
                    raise LedgerError('Session is not registered on blockchain')
                if kind in ('mark', 'manual', 'void') and any(e['type']=='close' and e['session_token']==session for e in events):
                    raise LedgerError('Session has been closed')
                if kind == 'close' and any(e['type']=='close' and e['session_token']==session for e in events):
                    raise LedgerError('Session is already closed')
                if kind in ('mark', 'manual') and any(e['type'] in ('mark', 'manual') and e['session_token']==session and e.get('student_token')==student for e in events):
                    raise LedgerError('Duplicate attendance rejected on-chain')
                if kind == 'void':
                    if not any(e['type'] in ('mark', 'manual') and e['session_token']==session and e.get('student_token')==student for e in events):
                        raise LedgerError('No attendance exists to flag')
                    if any(e['type']=='void' and e['session_token']==session and e.get('student_token')==student for e in events):
                        raise LedgerError('Attendance already flagged')
            current = self.blocks()
            when = datetime.now(timezone.utc).isoformat(timespec='seconds')
            payload = {'type': kind, 'session_token': session}
            if student is not None:
                payload['student_token'] = student
            if reason is not None:
                payload['reason_hash'] = hashlib.sha256(reason.encode('utf8')).hexdigest()
            unsigned = {'index': len(current) + 1,
                        'previous_hash': current[-1]['hash'] if current else '0'*64,
                        'created_at': when, 'payload': payload,
                        'public_key': self.public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()}
            block_hash = digest(unsigned)
            block = {**unsigned, 'hash': block_hash, 'signature': self.key.sign(bytes.fromhex(block_hash)).hex()}
            with self.path.open('a', encoding='utf8') as f:
                f.write(canonical(block).decode() + '\n')
                f.flush()
                os.fsync(f.fileno())
            return {'tx_hash': block_hash, 'block_number': block['index'], 'timestamp': when}

    def create_session(self, session_token):
        return self._append('create', session_token)
    def mark_attendance(self, session_token, student_token):
        return self._append('mark', session_token, student_token)
    def close_session(self, session_token):
        return self._append('close', session_token)
    def manual_attendance(self, session_token, student_token, reason):
        return self._append('manual', session_token, student_token, reason)
    def void_attendance(self, session_token, student_token, reason):
        return self._append('void', session_token, student_token, reason)
    def events(self):
        # Caller verifies before relying on events; never silently repair corruption.
        return [{**b['payload'], 'tx_hash': b['hash'], 'block_number': b['index'],
                 'timestamp': b['created_at']} for b in self.blocks()]

def get_ledger():
    from .config import env
    if env('CHAIN_BACKEND', 'local').lower() == 'ethereum':
        from .ethereum import EthereumLedger
        return EthereumLedger()
    return LocalLedger()
