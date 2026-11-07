# Policy Track: Senate Vote Tracker

See how your state's U.S. Senators voted over the last 4 years, with news articles and AI summaries for each policy.

Project scope, architecture and rules: [AGENTS.md](AGENTS.md).

## Run locally

Backend (FastAPI, Python 3.11+):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in the values
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

Frontend (Next.js, JavaScript):

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

App: http://localhost:3000
