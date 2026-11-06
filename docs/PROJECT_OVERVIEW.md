# University Mini Project — Technical Brief

**Title:** Blockchain-Based Secure Smart Attendance System Using Face Recognition

**Problem statement:** In a classroom, manually recording attendance consumes time, allows record-entry errors and makes it difficult for students to independently verify later edits. Existing centralized database attendance applications can also be changed by an administrator without a separate append-only audit trail.

**Goal:** Build a teacher-controlled camera-based attendance system with pseudonymous, tamper-evident class records and auditable corrections. Provide a manual, clearly labelled fallback when face recognition is unavailable.

## Components

- HTML/CSS/JavaScript dashboard, browser camera/image upload.
- Python FastAPI local backend and faculty login.
- OpenCV Haar detector and local binary pattern (LBP) similarity baseline.
- Private SQLite student registry and face-template store.
- HMAC-SHA256 pseudonym generator.
- Solidity `AttendanceLedger` smart contract on local Ganache test chain.
- Signed Ed25519 single-node hash-linked fallback.

## Testable functional requirements

1. Faculty may register a consenting student with three face samples.
2. Faculty may register a manual-only student without collecting biometrics.
3. One eligible face scan marks a student present in an active session.
4. Duplicate marks for a student/session are rejected by the ledger contract.
5. A faculty-only override must have a reason and a distinct event type.
6. A correction flags a bad record and leaves the original transaction visible.
7. Session closure prevents new marks.
8. Reports support all sessions, filtering and CSV export.
9. Local signed chain validates block hashes and signatures, refusing new writes when corrupted.

## Security improvements from blockchain

- **Append-only contract event model**: historical transaction trail for marks and corrections.
- **Authorization**: on-chain faculty role instead of anyone updating attendance table.
- **Duplicate checks**: smart contract state enforces uniqueness at consensus execution level on this private EVM.
- **Auditability**: transaction/block identifiers for validation against the running node.
- **Pseudonyms**: student identity and biometric data remain private, while public-contract entries are keyed HMAC tokens.

## Risks and research gaps

- Ganache has one operator and no independent validator network; it can be reset.
- Face photos and video playback can spoof the baseline detector; no liveness detection.
- Recognition can fail with lighting changes, occlusions, glasses or camera variation.
- Biometrics in local SQLite are sensitive; encrypted-at-rest storage is future work.
- Faculty themselves can submit a false mark. Ledger proves what was recorded, not whether it was true.
- To claim a recognition accuracy, conduct a consented validation experiment and report false acceptance and false rejection rates.

## Suggested evaluation

Record functional pass/fail test results, time to mark one student in local mode versus EVM mode, blockchain transaction hashes, duplicate rejection, correction trace, and a tampering experiment in the signed fallback. Collect consented image pairs for recognition evaluation. Never report invented accuracy measurements.

## Future work

Liveness detection, multi-person classroom scanning, decentralized permissioned validator network, encrypting templates at rest, institution SSO/role management, more robust embeddings, cross-device attendance, and deployment security review.
