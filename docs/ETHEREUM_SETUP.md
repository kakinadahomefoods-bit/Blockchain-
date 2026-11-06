# Real Solidity smart contract (private Ganache EVM)

## Simplest way on Windows

Double-click `START_PROJECT_WINDOWS.bat` from the extracted project directory. The PowerShell helper checks/installs Python, Node and project dependencies, starts Ganache on **127.0.0.1:8545**, compiles `contracts/AttendanceLedger.sol`, deploys the smart contract if this is a brand-new profile, and starts the faculty dashboard at **127.0.0.1:8000**.

First run needs internet. `winget` may require your permission and may be unavailable on managed school computers. Missing prerequisites can be installed manually from official Python/Node websites before relaunching.

**Your real EVM instance is LOCAL and private, not a public Ethereum mainnet or decentralized consensus network.** Do not call it immutable against the person who controls the machine or Ganache database.

## Manual steps (also for macOS/Linux)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-ethereum.txt
npm install
.venv/bin/python scripts/start_evm.py
```

Windows equivalents: `.venv\Scripts\python.exe` instead of `.venv/bin/python`. The launcher will reuse the private Ganache database in `data/evm/ganache_db`, and will not overwrite an existing `.env` or redeploy over a lost chain with existing attendance records.

If Ganache is already running on 8545 with chain ID 1337, `scripts/start_evm.py` will reuse that node. A conflicting process on port 8545 must be stopped first.

## EVM contract functions

- `setFaculty(address, bool)` — owner controls on-chain faculty roles.
- `createSession(bytes32)` — register pseudonymous session token.
- `markAttendance(bytes32, bytes32)` — one face-scan attendance per student/session.
- `manualMarkAttendance(bytes32, bytes32, bytes32)` — explicitly tagged faculty override with hashed reason.
- `flagAttendance(bytes32, bytes32, bytes32)` — auditable correction without deleting old mark.
- `closeSession(bytes32)` — prevent new marks and flags for closed session.

The backend sends `HMAC_SHA256(secret, type:UUID)` pseudonyms; **no images, names or roll numbers** are written into contract storage or events. A faculty role gives transaction permission; it does not prove the biometric scanner was honest.

## Backup and troubleshooting

**Back up together:** `.env`, `data/evm/attendance.sqlite3`, `data/evm/ganache_db`, and `data/login-info.txt`. Avoid sending any of these files to others. Losing private Ganache DB can invalidate historic transaction IDs; the launcher intentionally refuses to auto-redeploy when old EVM sessions exist.

Useful commands:

```bash
python -m pytest -q
python scripts/compile_contract.py
python scripts/deploy_contract.py
```

The compiler uses the locally installed `node_modules/.bin/solcjs`; the deploy script uses Web3.py and an unlocked **local-only Ganache test account**. Never publish this test account as a real-money wallet, reuse it for public networks, or open Ganache RPC to the LAN.
