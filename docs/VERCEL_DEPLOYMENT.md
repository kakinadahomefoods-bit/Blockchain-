# Vercel deployment fix

The Git repository contains the complete **local** BlockAttend project (Python/OpenCV, private SQLite and a Ganache Solidity contract). This is not natively deployable to a stateless Vercel Function.

To avoid crashing on startup, Vercel's FastAPI entrypoint is set to `cloud_entry:app` in `pyproject.toml`. It serves an explicitly labelled, interactive browser-only preview at `/`, and a structured `GET /health` response. The preview supports fictional demo enrolment, classroom sessions, manual marks, duplicate prevention, CSV export and a SHA-256 hash-linked browser audit trail. Browser state is neither cloud storage nor a decentralized chain.

Cloud API endpoints under `/api/` return a deliberate HTTP 503 instead of starting SQLite or demanding local secrets. This prevents accidental storage of real attendance or biometric data on Vercel's ephemeral disk.

The original local launchers and `python app.py` continue to run `app.main:app` with the complete locally initialized application.

For a full multi-user web application, add protected persistent database + object storage, biometric consent and deletion controls, authenticated faculty sessions, approved cloud face-recognition compute and an Ethereum-compatible RPC/contract deployment. Do **not** use `/tmp` as persistent storage.
