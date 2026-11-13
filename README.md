# BlockAttend — Blockchain-Based Secure Smart Attendance Using Face Recognition

**Presidency University | Computer Science and Engineering | Mini Project**

An editable, runnable local classroom **prototype**, not a hosted service. It combines a responsive faculty dashboard, consent-based student registration, webcam/photo scanning, OpenCV face recognition, a Solidity smart contract, local Ethereum (Ganache), private SQLite storage, audit trails, reports and tests.

## 🚀 Windows: extract ZIP → double-click launcher

1. Extract **the entire ZIP** to a normal folder. Don't run it from the ZIP preview.
2. Connect to the internet for the **first launch** so the free libraries can be installed.
3. Double-click **`START_PROJECT_WINDOWS.bat`** (recommended: actual Solidity smart contract and Ganache EVM).
4. The script checks for Python 3.11–3.13 and Node.js LTS, tries to install any missing runtime through Windows Package Manager (`winget`), sets up dependencies, starts Ganache, compiles the Solidity contract, deploys it, and opens the attendance dashboard.
5. A unique faculty password is created **on your own computer**. Retrieve it from **`data/login-info.txt`**, keep it private, and use it to sign in.
6. The dashboard opens at **http://127.0.0.1:8000**. Later, start the project by double-clicking the same file again.

**Important:** This ZIP contains complete source code and automated first-run installers, **not a pre-built Windows EXE**. First launch requires internet and may require accepting a `winget` installation prompt. If installation permissions are blocked by the school laptop, install Python 3.12 and Node.js LTS manually and rerun the launcher. We cannot verify Windows installation or your webcam in this Linux build environment.

### Lighter fallback (Python only)

Double-click **`START_OFFLINE_DEMO_WINDOWS.bat`**. This uses a locally signed hash-linked educational chain, which is **not** Ethereum and **not** decentralized. Use it only if Node/Ganache is unavailable, and label it honestly in your viva.

**Do not mix attendance data between modes.** The two launchers use separate databases in `data/local/` and `data/evm/`, while retaining the same private faculty login. Keep your `.env` and entire `data/` directory to preserve records and keys.

### macOS/Linux (real EVM)

Install Python 3.11–3.13 and Node.js 20+ first, then run:

```bash
bash START_PROJECT_MAC_LINUX.sh
```

For the signed single-node fallback: `bash START_OFFLINE_DEMO_MAC_LINUX.sh`.

## Product features

| Feature | How it works |
|---|---|
| Faculty login | Random password generated on first run, HttpOnly cookie, CSRF validation |
| Student enrolment | Three or more consenting face images, stored as LBP templates off-chain |
| No-camera enrolment | Manual-only student registration, no biometric collection |
| Face identification | OpenCV Haar face detector + uniform LBP histograms, reject uncertain matches |
| Class sessions | Create/close sessions with blockchain events |
| Smart contract | Authorized faculty writers, unique pseudonymous student ID per session, duplicate checks |
| Blockchain audit | Transaction hash, block number, event history and integrity checks |
| Manual fallback | Faculty can mark a registered student with a reason; event explicitly says manual |
| Corrections | Flag wrong records without hiding the original blockchain transaction |
| Reporting | Filter sessions, browse attendance, export CSV with transaction proofs |
| Responsive interface | Dark themed HTML/CSS/JavaScript dashboard supporting laptop browsers |

## How attendance is recorded

```text
   Webcam or consenting photo         Faculty-only manual override (optional)
                |                                      |
                v                                      v
       OpenCV face detection                   Pick registered student
                |                              and enter explanation
                v                                      |
         LBP descriptor                                |
                |                                      |
                v                                      |
       Match private templates                         |
                |                                      |
                +---------------+----------------------+
                                |
                                v
                  Faculty-authenticated Python API
                                |
                                v
             HMAC tokens (NO names/photos/rolls on-chain)
                                |
                 +--------------+-------------------+
                 |                                  |
                 v                                  v
        Solidity smart contract               Signed local hash chain
       on a PRIVATE Ganache EVM             (educational fallback only)
                 |                                  |
                 +-------------------+--------------+
                                     |
                                     v
                     Transaction receipt / CSV / explorer
```

The main recommended mode is a **single-machine Ganache Ethereum-compatible dev network**. It executes **real Solidity smart-contract transactions**, but it is not a public/independently decentralized blockchain. Network/operator trust still matters.

## Teacher demonstration (5–8 minutes)

1. Log in. Go to **Student enrolment**.
2. Register yourself or a consenting volunteer using **three distinct webcam shots** in good lighting, or register as **manual-only** if the camera is unavailable.
3. Go to **Scan attendance**. Create a class `Blockchain Lab`, course `FBT101`.
4. Select the session and enable the camera. Use **Check face only** to preview recognition.
5. Click **Scan & mark**. The system writes one event on the smart contract and shows transaction hash/block number.
6. Scan again to demonstrate **duplicate rejection**.
7. If you used manual-only registration, select the student, enter an explanation, and click **Record faculty override**; the report clearly says it was manual.
8. Open **Attendance reports** and export a CSV. Use **Flag error** to demonstrate correction without deleting the original.
9. Open **Blockchain explorer**, verify the ledger, and explain *what blockchain does and does not secure*.

## Why blockchain improves integrity

- **Authorization**: contract roles limit attendance writers to faculty-controlled accounts.
- **Duplicate rejection**: each session/student token can be marked only once.
- **Event log**: corrections add new transactions instead of silently overwriting attendance.
- **Verification**: transaction receipts, ordered event history and hashes can be inspected.
- **Minimized disclosures**: only 32-byte keyed pseudonyms are recorded on the EVM; names, roll numbers and LBP templates stay in private SQLite.

**Limits:** a private Ganache chain does not provide public-network consensus; its operator can reset its history. Blockchain cannot prevent photo spoofing, improve face recognition accuracy or verify that a teacher marks the correct student. The system intentionally labels faculty-only overrides.

## Developer commands

With a local Python virtual environment and Node/npm:

```bash
python -m pip install -r requirements-ethereum.txt -r requirements-dev.txt
npm install
python scripts/start_evm.py       # Starts Ganache and deploys contract when needed
python -m pytest -q              # Automated Python tests
node --check static/app.js        # Frontend syntax validation
```

For the signed demo: `python scripts/start_local.py`. For complete details, see `docs/ETHEREUM_SETUP.md` and `docs/LIMITATIONS.md`.

## Files and organization

- `START_PROJECT_WINDOWS.bat` — first-run setup + real Ganache / Solidity / Python server.
- `START_OFFLINE_DEMO_WINDOWS.bat` — fallback signed single-node chain.
- `scripts/windows_one_click.ps1` — automatic dependency checks and installation prompts.
- `scripts/start_evm.py` — persistent private EVM node, compile/deploy and backend startup.
- `app/` — local server, facial descriptor engine, database, contract API and ledger verification.
- `static/` — complete responsive app interface, camera/photo capture and report UI.
- `contracts/AttendanceLedger.sol` — readable Solidity source.
- `tests/` — unit/integration security and application tests.
- `docs/` — guides, limitations, architecture graphic, demo outline, Codex handoff.
- `.env` and `data/` — **generated at runtime; contains secrets and student data, do not share**.

## Security and ethical use

Use consenting test participants. Do not use real students' biometric data without permission. Raw images are processed and discarded; extracted face templates are local. Deleting an identity removes the local mapping, but already-written pseudonymous blockchain entries persist. Keep data and keys protected, avoid hosting publicly, do not expose port 8545 to the network, and have an instructor review recognition mistakes.

**Validation:** 12 automated tests currently pass in the supplied environment, including duplicate rejection, manual override, API authentication, CSV generation, tamper diagnostics and corrections. JavaScript parses successfully. The Windows bootstrapper, Solidity deployment and actual laptop webcam have **not** been executed in this environment; they must be verified on your computer. Do not claim a measured recognition accuracy without collecting and evaluating volunteer data.

**License:** MIT. This is a complete, modifiable **mini-project prototype**; not production-certified software.

## Student join flow — full local application

Faculty opens **Take attendance LIVE**, creates or selects a class and copies its
12-character student code / join link. Student opens `/join` on the **same
reachable backend**, enters the code and their registered roll number, and
submits a webcam image or consented photo. The server confirms that the matched
biometric identity belongs to that roll before marking attendance through
the configured real Ganache/Solidity contract (or signed local fallback).
The student receives a transaction receipt. The teacher refreshes the roster.
Duplicate attendance and submissions after the session closes are rejected.

The learner must first be enrolled with three consented face samples by faculty;
manual-only registrations can only receive a faculty-supervised override.
Codes for existing sessions are derived from the faculty's local HMAC secret and
are available when the class is selected after updating.

**Important**: The default server binds to 127.0.0.1, which is inaccessible to
students on other devices. Sharing a localhost link on a phone does not work;
cross-device use requires a secure reachable HTTPS deployment/tunnel and a
backend security review. Do not publish your local Ganache RPC or faculty
password. The Vercel hosted site remains a browser-only demo; no shared database
or biometric processing is running there. The Haar/LBP classroom face matcher
does not perform anti-spoofing/liveness checks.

## Faculty-issued student login and face-verified attendance

The **complete local application** has separate student authentication at
`http://127.0.0.1:8000/join`. Faculty signs in, enrols a consenting student
with three face samples, clicks **Create student login** beside that student's
record, and privately shares the one-time password and roll number.

Faculty creates an open class in **Take attendance LIVE** and shares the
12-character join code. Students sign in with their roll number and password,
enter the class code, consent to face-photo processing, and submit a webcam
frame or photo. The backend checks the **signed-in account identity** against
the facial template before creating one ledger attendance transaction.
Closed classes and duplicate marks are rejected; success displays a
block number and transaction hash. Faculty can reset a student account,
which invalidates previous passwords and student sessions. Students can
change their passwords (12+ characters).

Security: salted PBKDF2-HMAC-SHA256 credential hashes in the local SQLite
database, HttpOnly SameSite cookies, authenticated CSRF-protected endpoints,
and local login rate limiting. Webcam matching is a classroom prototype
without spoof/liveness detection and should not be used for grading without
manual oversight. Never share the generated `data/` files, private keys,
login passwords, or biometric templates.

**Online limitation:** Vercel hosts a browser-only preview and does not
provide this Python/OpenCV/Ganache backend or a shared database. Student
phones require the backend hosted behind HTTPS with persistent storage and
proper biometric data security. `127.0.0.1` is only accessible on the
computer running the local server.
