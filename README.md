# Policy Track: Senate Vote Tracker

See how your state's U.S. Senators voted over the last 4 years, with news articles and AI summaries for each policy.

Project scope, architecture and rules: [AGENTS.md](AGENTS.md).

## Run locally

Use two terminals in the same checkout, one for FastAPI and one for Next.js. Stop any earlier Next.js process before switching branches, then open the URL printed by the new process.

Backend (FastAPI, Python 3.11+):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in the values
python -m scripts.ingest --dry-run --limit 3   # check the data sources (writes nothing)
python -m scripts.ingest                       # load ~4 years of Senate votes into Firestore
uvicorn app.main:app --reload
```

Test the API by hand at http://localhost:8000/docs (click an endpoint, then **Try it out**).

On Windows PowerShell, run the backend with:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env # first run only, then fill in the values
.\.venv\Scripts\python.exe -m scripts.ingest --dry-run --limit 3
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

For live results, configure the Firestore credentials in `backend/.env`, ensure the indexes in `firestore.indexes.json` are available in the configured project, and run `python -m scripts.ingest` if the database has yet to be populated. In PowerShell, use the virtual environment’s Python executable shown above. The dry run verifies source access without writing to Firestore.

Frontend (Next.js, JavaScript):

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

App: http://localhost:3000

Set `NEXT_PUBLIC_API_URL` to the FastAPI origin if it differs from `http://localhost:8000`. Check `/api/states/UT/senators` on the backend to distinguish a populated delegation from missing data or credentials. The AI summary endpoint requires the separate DeepSeek implementation.
