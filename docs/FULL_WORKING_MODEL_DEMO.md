# BlockAttend — Full Working Model Demonstration

**Use `START_PROJECT_WINDOWS.bat` on a Windows laptop.** This is the real local FastAPI + OpenCV + Ganache/Solidity application. The Vercel URL is a separate browser-only preview and cannot perform face recognition or send smart contract transactions.

## Start

1. Download the project, extract it fully, and double-click `START_PROJECT_WINDOWS.bat`.
2. First run installs Python packages, Node packages, Ganache and Solidity compiler, and deploys `contracts/AttendanceLedger.sol` on a local Ethereum-compatible blockchain. Internet is needed for first installation.
3. Open `data/login-info.txt` to find the **generated** faculty password. Never post it publicly.
4. Browse to `http://127.0.0.1:8000` on the **same laptop** and sign in.

## 6-minute complete live demo

1. **Student enrolment:** Enter a fictional name/roll. Ask a consenting adult volunteer to stand in front of the webcam, enable the camera, capture **3 distinct images**, check voluntary consent, and click **Save student securely**. Their local face templates are stored in SQLite; not in blockchain.
2. **Take attendance · LIVE:** Open the sidebar's highlighted menu. Create a session (e.g. `Blockchain Lab`, `CSE402`), or choose an existing open session.
3. **Live roster:** The student appears as **PENDING** with counters for present students and class coverage.
4. **Actual recognition:** Enable the webcam, have the consenting enrollee face the camera, click **Check face only**, then **Recognize & mark PRESENT**. The server detects the face, computes an LBP descriptor, matches registered templates (or rejects if uncertain), and submits a Solidity transaction. Observe the block number and transaction hash.
5. **Proof:** The student becomes **PRESENT** in the real API-backed roster. Scan again to demonstrate duplicate prevention enforced by the smart contract.
6. **Reporting:** Open **Attendance reports**, then **Blockchain explorer**, verify transaction history and chain integrity, and export CSV.

## Safe fallback

If a face scan fails, select the student and enter a clear reason under **Faculty attendance override**. The ledger labels the method as manual and preserves an explanation hash. Never claim it is a face match.

## Technical boundaries

- Ganache executes genuine Solidity bytecode and real **local EVM transactions**, but it is a private developer chain, not a decentralized public network.
- Face recognition uses basic Haar + LBP. It is not liveness detection; photos can spoof it. Do not use it for real grading decisions without human verification.
- Never upload or commit `.env`, `data/`, student faces, private keys, or attendance databases.
- This model is intended for one laptop at the demonstration table. Vercel cannot persist local SQLite/Ganache state. Multi-user online use requires secure authentication, hosted database, managed RPC/provider, and privacy/security redesign.
