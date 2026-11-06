# Codex / coding assistant handoff

Open the extracted `BlockAttend_ReadyToRun` directory as your workspace. Source is fully editable.

**Task:** improve/test the academic blockchain-based attendance prototype. Keep privacy, consent, and the clear difference between **face scan** versus **faculty override**; do not fake measured performance or claim Ganache is decentralized.

## Most important files

- `app/main.py` — FastAPI routes, authentication, cookies, CSRF.
- `app/service.py` — user-facing business rules.
- `app/face_engine.py` — OpenCV Haar/LBP. This is a basic baseline (not liveness detection).
- `app/ethereum.py`, `contracts/AttendanceLedger.sol` — actual EVM smart contract path.
- `app/ledger.py` — single-node signed chain fallback.
- `scripts/start_evm.py`, `scripts/windows_one_click.ps1` — real-chain launcher.
- `static/index.html`, `static/styles.css`, `static/app.js` — dashboard.
- `tests/` — run `python -m pytest -q`; maintain and expand tests.

## Requested next checks on user's Windows laptop

1. Execute `START_PROJECT_WINDOWS.bat` from extracted folder, verify first-run package installation and saving login password.
2. Inspect Ganache startup output `data/evm/ganache.log` if needed.
3. Test webcam access from `http://127.0.0.1:8000` with consenting volunteer.
4. Verify Solidity deploy receipt and end-to-end `eth_chainId=1337` transaction.
5. Validate multi-student accuracy with consented data before discussing metrics.
6. Avoid committing generated `.env`, `data/`, `.venv/`, `node_modules/`, faces, keys or database.

Do not bypass faculty authorization, silently change attendance history, or upload biometric samples.
