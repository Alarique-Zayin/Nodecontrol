# Bitcoin Node Dashboard (MVP)

FastAPI backend + Tailwind/Chart.js frontend to monitor a local Bitcoin Core node via JSON-RPC.

Quick start (development):

1. Copy `.env.example` to `.env` and fill RPC credentials.
2. Install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Run the app:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` to view the dashboard.
