# Agent Guide: Senate Vote Tracker

Read this first. It is the source of truth for project scope. If a task isn't covered here or goes against it, stop and ask a human teammate instead of guessing. When the team changes a decision, update this file in the same change.

---

## 1. What we are building

A web app where a user picks a **U.S. state** and sees:

1. That state's **U.S. Senators** (current, plus anyone who held the seat in the time window).
2. The **Senate roll-call votes** each senator cast in the **last 4 years**, and the bill, resolution or nomination each vote was on.
3. **News articles** about each policy or bill.
4. An **AI summary** of each policy, made by **DeepSeek running on our private server**, that explains what the policy does and how the state's senators voted.

### Target user
A regular person who wants to know, without spin, how their senators voted.

### Definition of done (MVP)
- [ ] State picker (all 50 states) → state page listing its senators
- [ ] Senator page → list of their votes (newest first), filterable by date range and by vote position (Yea / Nay / Not Voting / Present)
- [ ] Policy/vote detail page → official info (title, date, result, tally), how each senator from the selected state voted, related articles, AI summary
- [ ] AI summary shows the sources it used and can be regenerated
- [ ] Works locally: frontend with `npm run dev`, backend with `uvicorn app.main:app --reload`, and network access to the DeepSeek server

---

## 2. Scope

### In scope
- **U.S. Senate only**, all 50 states
- **Rolling 4-year window**: from today minus 4 years to today. Compute it at runtime. Never hardcode dates. As of Nov 2026 this covers part of the 117th Congress (2nd session, 2022), the 118th (2023–2024) and the 119th (2025–2026).
- Roll-call votes on bills, resolutions, amendments and nominations
- News articles linked to a policy
- AI summaries and Q&A about a single policy, using our self-hosted DeepSeek

### Out of scope. Do not build these unless the team updates this file.
- House of Representatives, state legislatures, governors
- User accounts, login, saved favorites, notifications
- "Scores," grades, rankings, or any language that tells users which way to vote
- Predicting future votes
- Campaign finance, lobbying, polling data
- Third-party LLM APIs (OpenAI, Anthropic, DeepSeek's public cloud, etc.). The AI runs only on our private server.
- Native mobile apps
- Votes from before the 4-year window

---

## 3. Tech stack and architecture

```
Browser ──> Next.js frontend (React, JS) ──> FastAPI backend (Python) ──┬──> Congress.gov API
                                                                         ├──> senate.gov XML
                                                                         ├──> News API
                                                                         ├──> Firestore
                                                                         └──> DeepSeek (private server)
```

| Layer | Choice | Notes |
|---|---|---|
| Frontend | **Next.js App Router + React**, **JavaScript** | **Not TypeScript.** UI only: no database access and no external API calls |
| Backend | **FastAPI** (Python 3.11+) | All data fetching, Firestore, news and AI calls live here |
| HTTP client (backend) | `httpx` (async) | |
| Data validation | Pydantic v2 models | They mirror the data model in §5 |
| XML parsing | `lxml` or the standard-library `xml.etree.ElementTree` | For senate.gov vote files |
| Database/cache | **Cloud Firestore** via the Python `firebase-admin` SDK | See §5.1 |
| AI | **DeepSeek** on our **private server** | See §6 |
| Backend tests | `pytest` | |
| Styling | Team's choice (Tailwind recommended) | Keep it consistent once picked |

**The frontend only ever talks to the FastAPI backend.** Secrets (API keys, Firebase credentials, DeepSeek URL/key) live only in the backend.

---

## 4. Data sources (all called from the backend)

### 4.1 Congress.gov API (bills, members, summaries)
- Base URL: `https://api.congress.gov/v3`. Free key from https://api.data.gov/signup. Env var `CONGRESS_API_KEY`.
- Rate limit: about 5,000 requests per hour. **Cache responses**, and never re-fetch the same bill on every page load.
- Useful endpoints:
  - `GET /member/congress/{congress}/{stateCode}` returns members by state (filter to Senate)
  - `GET /member/{bioguideId}` returns member details
  - `GET /bill/{congress}/{billType}/{billNumber}` returns bill details
  - `GET /bill/{congress}/{billType}/{billNumber}/summaries` returns CRS summaries (**main AI grounding text**)
  - `GET /bill/{congress}/{billType}/{billNumber}/actions`
- **Important:** Congress.gov does **not** provide Senate roll-call votes. Get those from senate.gov (4.2).

### 4.2 Senate.gov roll-call vote XML (the votes)
- Vote list per session:
  `https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_{congress}_{session}.xml`
- Single vote detail, with each senator's position:
  `https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{session}/vote_{congress}_{session}_{voteNumber5digits}.xml`
  (example: `vote_119_1_00042.xml`)
- In these files, senators are identified by **`lis_member_id`** (like `S354`), **not** bioguide ID.
- No API key is needed. Be polite: throttle requests and cache aggressively. Past votes never change.
- **senate.gov often blocks automated requests (HTTP 403).** The ingest tries senate.gov first and, if blocked, falls back to Voteview for that session (4.2b). Do not try to get around the block (no fake browser user agents).

### 4.2b Voteview (fallback for votes)
- UCLA's public roll-call dataset, built from official Senate records. No key needed. Files per Congress:
  `https://voteview.com/static/data/out/{rollcalls|votes|members}/S{congress}_{kind}.csv`
- `clerk_rollnumber` is the official Senate vote number, so vote IDs match senate.gov (`119-1-00042`).
- Cast codes: 1 = Yea, 6 = Nay, 7/8 = Present, 2–5 and 9 = Not Voting (paired/announced votes are not cast votes), 0 = not a member.
- `members` CSV has `bioguide_id`, so no LIS mapping is needed. Voteview has no time of day; dates are stored as noon US Eastern.
- Code: `backend/app/services/voteview/`.

### 4.3 ID mapping (LIS ↔ Bioguide)
- Use the public `unitedstates/congress-legislators` dataset (`legislators-current` and `legislators-historical`, JSON or YAML). It includes `id.lis`, `id.bioguide` and term/state info, and it also covers senators who left office during the window.
- **Canonical senator ID in our app = `bioguideId`.** Convert LIS IDs during ingest.

### 4.4 News articles
- Provider: **GNews** (`https://gnews.io/api/v4/search`, free tier 100 requests/day), behind one adapter in `backend/app/services/news/` so it can be swapped.
- Env var `NEWS_API_KEY`. The query is the short title, the nominee's name for nominations, or the bill number (e.g. `"S. 316" Senate`) when the title is a long official one.
- Store only the title, source, URL, published date and short description. **Do not scrape or store full article text.** Link out to the publisher.

### Linking a vote to a policy
Senate vote XML includes a `<document>` block (type and number, e.g. `S. 870`, `H.R. 2`, `PN 123`). Normalize it to our `policyId` format: `{congress}-{billType}-{number}` (e.g. `118-hr-2`). Nomination votes use `{congress}-pn-{number}`. Some votes (procedural votes, motions) have no document. Show them, but skip articles and AI for them.

---

## 5. Core data model

These are the shared contract between frontend and backend, so don't rename fields without updating this file. Define each one as a Pydantic model in `backend/app/models/`.

**Field names in JSON are camelCase** (as below), even though Python code uses snake_case. Use a Pydantic alias generator (`alias_generator=to_camel`, `populate_by_name=True`) and return responses by alias.

```js
// Senator
{ bioguideId, lisId, name, party, state, inOfficeFrom, inOfficeTo /* null if current */, photoUrl }

// Vote (one Senate roll call)
{ voteId /* "119-1-00042" */, congress, session, voteNumber, date, question, result,
  policyId /* nullable */, tally: { yea, nay, present, notVoting } }

// SenatorVote (name, party, state are optional display fields)
{ voteId, bioguideId, position /* "Yea" | "Nay" | "Present" | "Not Voting" */, name, party, state }

// Policy
{ policyId, congress, type, number, title, shortTitle, crsSummary, congressGovUrl,
  latestAction /* { date: "YYYY-MM-DD", text } | null */ }

// Article
{ policyId, title, source, url, publishedAt, description }

// AiSummary
{ policyId, model, generatedAt, summary, keyPoints: [], sources: [] }
```

Dates in API responses are ISO 8601 strings.

### 5.1 Firestore layout

| Collection path | Doc ID | Contents |
|---|---|---|
| `senators` | `bioguideId` | `Senator` |
| `senators/{bioguideId}/votes` | `voteId` | `Vote` fields copied in + `position` (lets the senator page load with one query) |
| `votes` | `voteId` | `Vote` + `positions: { [bioguideId]: position }` + `members: SenatorVote[]` |
| `policies` | `policyId` | `Policy` + `articlesFetchedAt` |
| `policies/{policyId}/articles` | hash of the article URL | `Article` + `fetchedAt` |
| `aiSummaries` | `{policyId}__{model}` (`:` and `/` in the model name become `_`) | `AiSummary` |
| `meta` | e.g. `ingest` | last ingested vote per congress/session, used for incremental updates |

Rules:
- **Only the backend talks to Firestore**, using the Python `firebase-admin` SDK in `backend/app/db/`. Set the security rules to deny all client reads and writes.
- Store fields in camelCase, matching §5.
- Store dates as Firestore `Timestamp`s (Python `datetime` with a timezone) so queries can filter and sort by date.
- Vote lists sort by `date desc, voteNumber desc` and need the **composite indexes** in `firestore.indexes.json` (deploy them with `firebase deploy --only firestore:indexes`).
- All Firestore code lives in `backend/app/db/repository.py`. Routers get it through the `get_repo` dependency, which returns `503` if Firebase isn't configured.
- Use **batched writes** (max 500 operations per batch) during ingest.
- Keep reads low and never read a whole collection on a request. Senator vote pages use `offset()` + `limit()` so the API can take a page number (at most ~1,600 votes per senator, so the skipped reads stay small).
- **Write cost:** each vote is ~101 writes (the vote + one copy per senator), so a full 4-year ingest is roughly 270,000 writes. That's over the free Spark plan's 20,000 writes/day; use the Blaze plan (about $0.50 for the full load) or ingest over several days with `--congress`.
- Articles are cached for 24 hours. Votes and policies are written once and not re-fetched.

---

## 6. AI: DeepSeek on our private server

- DeepSeek is **hosted on a private server we control**. Only the backend calls it. The browser never sees the server URL or key.
- Assume an **OpenAI-compatible chat completions API** (`POST {DEEPSEEK_BASE_URL}/chat/completions`). vLLM, Ollama and SGLang all provide one. Call it with `httpx` or the `openai` Python client pointed at `DEEPSEEK_BASE_URL`. If the server uses a different API, update this section.
- Env vars (backend only): `DEEPSEEK_BASE_URL`, `DEEPSEEK_API_KEY` (sent as a `Bearer` token), and `DEEPSEEK_MODEL` (the model name the server exposes).
- **Never commit the server address or key.** Don't paste them into issues, PRs or chat logs.
- If the model is a reasoning model (`deepseek-r1`), its reasoning comes back either in a `<think>...</think>` block or in a separate `reasoning_content` field. **Remove or ignore it** before parsing or storing, and never show it to users.
- Ask for JSON output (`response_format: {"type": "json_object"}` if the server supports it, otherwise a strict instruction in the prompt). Validate it with the `AiSummary` Pydantic model, and retry once if it doesn't parse.
- Set a request timeout (e.g. 60 s). The server may be slow or busy.
- **Grounding:** the prompt may only use our data, meaning the CRS summary, bill title and actions, vote result and tally, how the state's senators voted, and article titles and descriptions. Tell the model to answer only from the provided context and to say "not enough information" otherwise.
- **Output** must match the `AiSummary` shape: a plain-language summary (about 150 words), 3–5 key points, and a `sources` list of what it used.
- **Neutral tone:** no opinions, no "good/bad" judgments, no telling the user how to feel or vote.
- **Cache** summaries in Firestore `aiSummaries`, keyed by `policyId + model`. Regenerate only when the user clicks "Regenerate."
- **Stream** to the UI with FastAPI `StreamingResponse` if easy. If not, show a loading state.
- If the DeepSeek server is down or times out, the API returns a clear error (`503` with a message). The rest of the app must still work.
- Optional stretch goal: "Ask about this policy" chat that uses the same grounding rules.

---

## 7. Backend API (FastAPI)

- Every route is under `/api`. All return JSON with camelCase fields (§5).
- Errors use the shape `{ "error": { "code", "message" } }` with a correct HTTP status. Add an exception handler so FastAPI's default `{"detail": ...}` errors are converted to this shape.
- Enable CORS only for the frontend origin (`FRONTEND_ORIGIN`).
- FastAPI's auto docs at `/docs` are the live reference. Keep route summaries accurate.

| Method & path | Returns |
|---|---|
| `GET /api/health` | `{ status, deepseek: "up" \| "down" }` |
| `GET /api/states/{stateCode}/senators` | `Senator[]` for that state in the window |
| `GET /api/senators/{bioguideId}` | `Senator` |
| `GET /api/senators/{bioguideId}/votes?from=&to=&position=&page=&pageSize=` | `{ items: (Vote & { position })[], page, pageSize, total }`. Dates are `YYYY-MM-DD`, clamped to the window; `pageSize` defaults to 25, max 100 |
| `GET /api/votes/{voteId}` | `Vote` + `senatorVotes: SenatorVote[]` (sorted by state, then name) |
| `GET /api/policies/{policyId}` | `Policy` + `votes: Vote[]` (newest first) |
| `GET /api/policies/{policyId}/articles` | `Article[]`, newest first. Cached 24 h; stale cache is served if GNews fails, otherwise `503` |
| `POST /api/ai/summary` body `{ policyId, stateCode?, regenerate? }` | `AiSummary` |

The frontend reads the backend URL from `NEXT_PUBLIC_API_URL` and keeps all fetch calls in `frontend/lib/api.js`.

---

## 8. Project structure

```
/frontend                         # Next.js app (JavaScript)
  /app
    page.js                       # home: state picker
    /state/[stateCode]/page.js
    /senator/[bioguideId]/page.js
    /policy/[policyId]/page.js
  /components                     # React UI components
  /lib/api.js                     # the only place that calls the backend
  package.json
  .env.example

/backend                          # FastAPI app (Python)
  /app
    main.py                       # FastAPI app, CORS, error handlers, routers
    config.py                     # env settings (pydantic-settings)
    deps.py                       # FastAPI dependencies (get_repo, get_http)
    date_window.py                # single source for the 4-year window
    states.py                     # the 50 state codes
    /routers/                     # one file per resource (states, senators, votes, policies, ai)
    /models/                      # Pydantic models from §5
    /services/
      http.py                     # shared httpx client (User-Agent, timeouts)
      vote_types.py               # source-neutral ParsedVote + policyId helpers
      /congress/                  # Congress.gov client
      /senate/                    # senate.gov XML fetch + parse
      /voteview/                  # Voteview CSV fallback
      /legislators/               # senators in window + LIS <-> bioguide mapping
      /news/                      # GNews adapter
      /ai/                        # DeepSeek client + prompt builders (AI teammate)
    /db/
      __init__.py                 # firebase-admin init (async Firestore client)
      repository.py               # every Firestore read/write
  /scripts/ingest.py              # pulls senators, votes, policies into Firestore (see --help)
  /tests                          # pytest
    /fixtures                     # saved sample XML/CSV/JSON
  requirements.txt
  .env.example

firestore.rules                   # deny all client access
firestore.indexes.json            # composite indexes
AGENTS.md
CLAUDE.md
```

---

## 9. Rules for agents

1. **Stay in scope.** If a request touches §2 "Out of scope," stop and flag it.
2. **Languages:** JavaScript for `frontend/` (no TypeScript), Python for `backend/`. No other languages.
3. **No secrets in code or commits.** Read them from env vars (`.env.local` for the frontend, `.env` for the backend; both are gitignored). Add any new var to the matching `.env.example`. Never commit a Firebase service-account JSON file or the DeepSeek server URL/key.
4. **Only the backend calls external services** (Congress.gov, senate.gov, news, Firestore, DeepSeek), and always through the cache. The frontend calls only our FastAPI API, through `frontend/lib/api.js`.
5. **Only `NEXT_PUBLIC_API_URL` may be exposed to the browser.** Never put a secret in a `NEXT_PUBLIC_` variable.
6. **Use the shared data model (§5) and API contract (§7).** If you must change them, update this file and both sides (Pydantic model and frontend usage) in the same change.
7. **Use `backend/app/date_window.py`** for the 4-year window everywhere. Don't recompute it ad hoc.
8. **Neutral, factual UI copy.** Show official vote data as-is.
9. **Fail gracefully.** If news or AI is down, the vote data still renders.
10. **Keep changes small and focused**, one feature per branch/PR. Frontend and backend work can go in separate PRs, as long as the contract in §7 is respected. Don't refactor teammates' areas without asking.
11. **Python style:** type hints everywhere, `async` route handlers and `httpx.AsyncClient`, format with `ruff` (or `black`). Pin dependencies in `requirements.txt`.
12. **Don't add heavy dependencies** without noting why in the PR.
13. **Test the parsers** (`services/senate`, `services/voteview`, ID mapping, policyId normalization) with pytest and saved fixtures in `backend/tests/fixtures`, not live calls. Use `httpx.MockTransport` for HTTP clients, override `get_repo` with a fake repository for route tests, and mock the DeepSeek client.

---

## 10. Open decisions (team to fill in)

| Decision | Options | Decided |
|---|---|---|
| Backend | FastAPI (Python) | **Decided** |
| Database | Cloud Firestore | **Decided** |
| AI model | DeepSeek on our private server | **Decided**. Serving stack (vLLM / Ollama / other) and exact model TBD |
| News provider | GNews | **Decided** |
| Vote source | senate.gov XML, falling back to Voteview when blocked | **Decided** |
| Ingest strategy | Pre-ingest with `backend/scripts/ingest.py`; API reads only Firestore (plus GNews for articles) | **Decided** |
| Styling | Tailwind / CSS Modules | _TBD_ |
| Deployment | Where the frontend and backend are hosted | _TBD_ |

---

## 11. Environment variables

**Backend** (`backend/.env`, never exposed to the browser):
```
CONGRESS_API_KEY=
NEWS_API_KEY=

DEEPSEEK_BASE_URL=        # e.g. https://<private-server>/v1
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=

FIREBASE_PROJECT_ID=
FIREBASE_CLIENT_EMAIL=
FIREBASE_PRIVATE_KEY=     # keep the \n escapes; replace them with real newlines in code

FRONTEND_ORIGIN=http://localhost:3000
```

**Frontend** (`frontend/.env.local`):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```
