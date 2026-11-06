# Security, privacy, and evaluation limits

## Precise distinction between modes

- **Local mode** (`CHAIN_BACKEND=local`): Ed25519-signed, SHA-256-linked append-only ledger. Blocks are verified from genesis. This is a local educational prototype **without distributed consensus**. An administrator controlling both ledger and signing key can replace history; deleting all blocks will also reset the local history. Stronger protection needs independent network validators, anchored hash checkpoints and separated key custody.
- **Ethereum/Ganache mode** (`CHAIN_BACKEND=ethereum`): Solidity code runs in EVM with faculty authorization, on-chain duplicate checks, event logs and timestamps. Ganache is a private single-operator development chain, so it is not equivalent to a public blockchain. We could not run/test this mode in the packaging environment because Solidity/Web3/npm packages were unavailable offline.

## Face recognition (most important limitation)

Haar face detection + uniform Local Binary Pattern histogram comparison is a simple, offline classical computer-vision approach. Its accuracy can change significantly with camera angle, lighting, appearance, pose and similar-looking faces. It has **no blink, depth or liveness detection**: a printed photo or screen might fool it. Match threshold defaults are illustrative, not scientifically calibrated. Never use predicted identity without teacher oversight where grades, attendance or discipline decisions are affected.

## Biometric privacy

- Do not register anybody without permission and a legitimate purpose.
- Name, roll number, consent timestamp and histogram face descriptors are stored locally in `data/attendance.sqlite3`.
- The app does **not** store raw submitted photos on disk. LBP histograms are still biometric-derived data: restrict filesystem access, do not email/share the `data/` folder.
- Students can be deleted from the local database via the faculty dashboard, but their pseudonymous historical blockchain events cannot be erased. A university production deployment would need a real data-retention, notice, access-control and legal-compliance review.
- Secure HTTPS is required for any access beyond localhost; the project binds to localhost by default and is **not hardened for exposure on the public internet**.

## Threat model and improvement

| Threat | Plain unprotected DB | BlockAttend local ledger | EVM smart contract mode |
|---|---|---|---|
| Edit a past attendance entry | Possible for DB editor | Detected if signed history modified | Event log modification requires chain rewrite (depends on network security) |
| Mark same student twice in a class | Application rule required | Rejected at ledger layer | Rejected by contract |
| Unauthorized writer | DB ACL/application credentials | Faculty login + validator private key | Faculty-only contract functions |
| Biometric theft | Risk if stored | Risk still exists off-chain | Same off-chain risk |
| Photo replay/spoof | Not inherently solved | Not solved | Not solved |
| Malicious server/validator admin | Controls DB | Can replace entire history/key | Local Ganache operator can rewrite chain |

## Honest claims for your viva

- Say: "Blockchain adds an auditable, tamper-evident transaction history and smart-contract enforcement in EVM mode."
- Avoid saying: "No one can ever alter attendance" or "Face recognition prevents all proxy attendance".
- Say: "Our offline mode is useful for demonstrations; real-world multi-node deployment and biometric anti-spoofing would be future work."
