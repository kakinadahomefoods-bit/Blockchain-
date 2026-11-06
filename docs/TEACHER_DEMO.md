# Teacher demonstration script (8–12 minutes)

**Project title:** Blockchain-Based Secure Smart Attendance System Using Face Recognition and Computer Vision

**Problem statement:** Manual attendance takes time and can be changed in an unprotected record store. The project explores automatic recognition and a cryptographically verifiable attendance history.

**Objective:** Demonstrate (a) voluntary student enrolment, (b) single-face matching, (c) authorized ledger writes, (d) duplicate prevention, (e) audit verification, and (f) correction without deleting original evidence.

**Suggested live demo:**
1. Open dashboard and describe the identity/database vs ledger separation (30 sec).
2. Register a consenting volunteer with 3 webcam shots (2 mins).
3. Create a session; show an on-chain `SessionCreated` or `create` event (1 min).
4. Scan volunteer and mark attendance; show transaction hash/block number (1 min).
5. Try again, demonstrate duplicate rejection (30 sec).
6. Export records and flag an incorrect mark; show that a correction event is added (1 min).
7. Verify chain, and (in a copied disposable dataset) demonstrate that changing a block's JSON causes the verifier to reject it. Never tamper with your only copy! (1 min).
8. Explain limitations: local chain is not decentralized; photo spoofing and recognition errors remain risks (1 min).

**Sample viva questions**

1. **Why blockchain?** To make edits detectable and enable independent event auditing; Ethereum mode also moves duplicate/faculty enforcement into a smart contract.
2. **What is a block hash?** A SHA-256 digest of canonical block fields, bound to the preceding block's hash.
3. **How is a student identified without storing names on-chain?** A random UUID is mapped to an HMAC-SHA256 token with a secret key kept off-chain.
4. **What is a smart contract?** Code deployed to an EVM that validates state transitions, role permissions and duplicate marks.
5. **Does blockchain make face recognition more accurate?** No; it protects downstream record integrity, not biometric correctness.
6. **Why not put face images on blockchain?** Privacy, immutability and high storage costs; keep sensitive templates under controlled off-chain retention.
7. **What is a correction event?** An auditable flag that supplements but does not erase the original mark.
8. **What stops a proxy attacker with a printed face?** Nothing in this baseline; liveness checks and teacher supervision are needed.
9. **Which consensus algorithm is used?** Local mode is single-signer, so no distributed consensus; Ganache uses a local dev-chain transaction order. Do not claim Proof-of-Work or Proof-of-Stake.
10. **How do you evaluate the face classifier?** Enrol volunteer participants and measure precision/recall, false accept/reject rates under varied light, pose and camera conditions; current demo thresholds require calibration.

**What is completed vs future work:** The repo contains the full prototype and automated tests. Device-based recognition and Ethereum deployment must be tested on the presentation computer. Future work: multi-node permissioned chain, actual liveness checks, encryption at rest, secure shared-host deployment and a documented human appeal process.
