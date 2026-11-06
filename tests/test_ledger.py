import json
import pytest
from app.ledger import LocalLedger, LedgerError, token

def test_signed_chain_and_duplicate_protection():
    chain = LocalLedger()
    sid, alice = token('session', 'random-session'), token('student', 'random-student')
    first = chain.create_session(sid)
    marked = chain.mark_attendance(sid, alice)
    assert first['block_number']==1
    assert marked['block_number']==2
    assert marked['tx_hash'] != first['tx_hash']
    with pytest.raises(LedgerError, match='Duplicate'):
        chain.mark_attendance(sid, alice)
    chain.void_attendance(sid,alice,'recognition error')
    with pytest.raises(LedgerError,match='already flagged'):
        chain.void_attendance(sid,alice,'another reason')
    chain.close_session(sid)
    assert chain.verify()['valid'] is True
    with pytest.raises(LedgerError,match='closed'):
        chain.mark_attendance(sid,token('student','different'))
    with pytest.raises(LedgerError,match='closed'):
        chain.void_attendance(sid,alice,'too late')

def test_tamper_detection_and_write_lock():
    chain=LocalLedger()
    sid=token('session','a')
    chain.create_session(sid)
    path=chain.path
    lines=path.read_text().splitlines()
    block=json.loads(lines[0]); block['payload']['session_token']='f'*64
    path.write_text(json.dumps(block)+'\n')
    verification=chain.verify()
    assert verification['valid'] is False
    with pytest.raises(LedgerError,match='integrity'):
        chain.create_session(token('session','b'))

def test_tokens_hide_identity_and_domain_separated():
    assert token('student','person') != token('session','person')
    assert len(token('student','person')) == 64
    assert 'person' not in token('student','person')

def test_unknown_session_rejected():
    chain=LocalLedger()
    with pytest.raises(LedgerError,match='not registered'):
        chain.mark_attendance(token('session','unknown'), token('student','student'))
