# Agent Guide: Senate Vote Tracker

Read this first. It is the source of truth for project scope. If a task isn't covered here or goes against it, stop and ask a human teammate instead of guessing. When the team changes a decision, update this file in the same change.

---

## 1. What we are building

A web app where a user picks a **U.S. state** and sees:

1. That state's **U.S. Senators** (current, plus anyone who held the seat in the time window).
2. The **Senate roll-call votes** each senator cast in the **last 4 years**, and the bill, resolution or nomination each vote was on.
3. **News articles** about each policy or bill.
4. An **AI summary** of each policy, made by a **local LLM**, that explains what the policy does and how the state's senators voted.

### Target user
A regular person who wants to know, without spin, how their senators voted.

### Definition of done (MVP)
- [ ] State picker (all 50 states) → state page listing its senators
- [ ] Senator page → list of their votes (newest first), filterable by date range and by vote position (Yea / Nay / Not Voting / Present)
- [ ] Policy/vote detail page → official info (title, date, result, tally), how each senator from the selected state voted, related articles, AI summary
- [ ] AI summary shows the sources it used and can be regenerated
- [ ] Works locally with `npm run dev` plus a local LLM running

---

## 2. Scope

### In scope
- **U.S. Senate only**, all 50 states
- **Rolling 4-year window**: from today minus 4 years to today. Compute it at runtime. Never hardcode dates. As of Nov 2026 this covers part of the 117th Congress (2nd session, 2022), the 118th (2023–2024) and the 119th (2025–2026).
- Roll-call votes on bills, resolutions, amendments and nominations
- News articles linked to a policy
- Local AI summaries and Q&A about a single policy

### Out of scope. Do not build these unless the team updates this file.
- House of Representatives, state legislatures, governors
- User accounts, login, saved favorites, notifications
- "Scores," grades, rankings, or any language that tells users which way to vote
- Predicting future votes
- Campaign finance, lobbying, polling data
- Paid or cloud LLM APIs (the AI must run locally)
- Native mobile apps
- Votes from before the 4-year window

---

## 3. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | **JavaScript** (ES modules) | **Not TypeScript.** Use JSDoc for types where helpful. |
| Frontend | **React** in **Next.js App Router** pages | Both live in a single Next.js app |
| API | **Next.js Route Handlers** (`app/api/**/route.js`) | All external calls happen here, never in the browser |
| Local AI | **DeepSeek** (`deepseek-r1`) running locally through **Ollama** at `http://localhost:11434` | See §6 |
| Database/cache | **Cloud Firestore** via `firebase-admin` (server only) | See §5.1 |
| Styling | Team's choice (Tailwind recommended) | Keep it consistent once picked |

---

## 4. Data sources

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

### 4.3 ID mapping (LIS ↔ Bioguide)
- Use the public `unitedstates/congress-legislators` dataset (`legislators-current` and `legislators-historical`, JSON or YAML). It includes `id.lis`, `id.bioguide` and term/state info, and it also covers senators who left office during the window.
- **Canonical senator ID in our app = `bioguideId`.** Convert LIS IDs during ingest.

### 4.4 News articles
- Use a news search API behind one adapter, `lib/news/`, so the provider can be swapped. Candidates are NewsAPI.org, GNews and The Guardian Open Platform. **Decide as a team (§10).**
- Env var `NEWS_API_KEY`. Search by bill title, short title or bill number.
- Store only the title, source, URL, published date and short description. **Do not scrape or store full article text.** Link out to the publisher.

### Linking a vote to a policy
Senate vote XML includes a `<document>` block (type and number, e.g. `S. 870`, `H.R. 2`, `PN 123`). Normalize it to our `policyId` format: `{congress}-{billType}-{number}` (e.g. `118-hr-2`). Nomination votes use `{congress}-pn-{number}`. Some votes (procedural votes, motions) have no document. Show them, but skip articles and AI for them.

---

## 5. Core data model

Plain JS objects. These names are the shared contract between frontend and API, so don't rename fields without updating this file.

```js
// Senator
{ bioguideId, lisId, name, party, state, inOfficeFrom, inOfficeTo /* null if current */, photoUrl }

// Vote (one Senate roll call)
{ voteId /* "119-1-00042" */, congress, session, voteNumber, date, question, result,
  policyId /* nullable */, tally: { yea, nay, present, notVoting } }

// SenatorVote
{ voteId, bioguideId, position /* "Yea" | "Nay" | "Present" | "Not Voting" */ }

// Policy
{ policyId, congress, type, number, title, shortTitle, crsSummary, congressGovUrl }

// Article
{ policyId, title, source, url, publishedAt, description }

// AiSummary
{ policyId, model, generatedAt, summary, keyPoints: [], sources: [] }
```

### 5.1 Firestore layout

| Collection path | Doc ID | Contents |
|---|---|---|
| `senators` | `bioguideId` | `Senator` |
| `senators/{bioguideId}/votes` | `voteId` | `Vote` fields copied in + `position` (lets the senator page load with one query) |
| `votes` | `voteId` | `Vote` + `positions: { [bioguideId]: position }` |
| `policies` | `policyId` | `Policy` |
| `policies/{policyId}/articles` | hash of the article URL | `Article` + `fetchedAt` |
| `aiSummaries` | `{policyId}__{model}` (`:` in the model name becomes `_`) | `AiSummary` |
| `meta` | e.g. `ingest` | last ingested vote per congress/session, used for incremental updates |

Rules:
- **Use the Firebase Admin SDK only on the server** (`lib/db/`). The browser never talks to Firestore directly. Set the security rules to deny all client reads and writes.
- Store dates as Firestore `Timestamp`s so queries can filter and sort by date.
- Filtering a senator's votes by `position` and sorting by `date` needs a **composite index** on `senators/*/votes` (`position` + `date desc`). Keep it in `firestore.indexes.json`.
- Use **batched writes** (max 500 operations per batch) during ingest.
- Keep reads low. Paginate with `limit()` + `startAfter()`, and never read a whole collection on a page load.
- Articles are cached for 24 hours. Votes and policies are written once and not re-fetched.

---

## 6. Local AI agent

- The model is **DeepSeek**, run locally via **Ollama** (`ollama pull deepseek-r1:8b`). Env vars: `OLLAMA_URL` (default `http://localhost:11434`) and `OLLAMA_MODEL` (default `deepseek-r1:8b`; use a larger tag such as `deepseek-r1:14b` if the machine can handle it).
- `deepseek-r1` writes its reasoning inside `<think>...</think>` before the answer. **Remove that block** before parsing or storing the output, and never show it to users.
- Ask for JSON output (Ollama `format: "json"` or a JSON schema) so the result parses straight into `AiSummary`. Validate it, and retry once if it doesn't parse.
- Call it **only from server route handlers** (`/api/ai/...`), never from the browser.
- **Grounding:** the prompt may only use our data, meaning the CRS summary, bill title and actions, vote result and tally, how the state's senators voted, and article titles and descriptions. Tell the model to answer only from the provided context and to say "not enough information" otherwise.
- **Output** must match the `AiSummary` shape: a plain-language summary (about 150 words), 3–5 key points, and a `sources` list of what it used.
- **Neutral tone:** no opinions, no "good/bad" judgments, no telling the user how to feel or vote.
- **Cache** summaries in Firestore `aiSummaries`, keyed by `policyId + model`. Regenerate only when the user clicks "Regenerate."
- **Stream** responses to the UI if easy. If not, show a loading state. Ollama may be slow.
- If Ollama isn't running, the API returns a clear error (`503` with a message). The rest of the app must still work.
- Optional stretch goal: "Ask about this policy" chat that uses the same grounding rules.

---

## 7. Internal API (Next.js route handlers)

All return JSON. Errors use the shape `{ error: { code, message } }` with a correct HTTP status.

| Method & path | Returns |
|---|---|
| `GET /api/states/{stateCode}/senators` | `Senator[]` for that state in the window |
| `GET /api/senators/{bioguideId}` | `Senator` |
| `GET /api/senators/{bioguideId}/votes?from=&to=&position=&page=` | paginated `{ items: (Vote & { position })[], page, total }` |
| `GET /api/votes/{voteId}` | `Vote` + all `SenatorVote`s |
| `GET /api/policies/{policyId}` | `Policy` + its `Vote[]` |
| `GET /api/policies/{policyId}/articles` | `Article[]` |
| `POST /api/ai/summary` body `{ policyId, stateCode?, regenerate? }` | `AiSummary` |

---

## 8. Suggested project structure

```
/app
  page.js                         # home: state picker
  /state/[stateCode]/page.js
  /senator/[bioguideId]/page.js
  /policy/[policyId]/page.js
  /api/...                        # route handlers from §7
/components                       # React UI components
/lib
  /congress/                      # Congress.gov client
  /senate/                        # senate.gov XML fetch + parse
  /legislators/                   # LIS <-> bioguide mapping
  /news/                          # news provider adapter
  /ai/                            # Ollama/DeepSeek client + prompt builders
  /db/                            # firebase-admin init + Firestore read/write helpers
  dateWindow.js                   # single source for the 4-year window
/scripts
  ingest.js                       # pulls senators, votes, policies into Firestore
/test/fixtures                    # saved sample XML/JSON for parser tests
firestore.rules                   # deny all client access
firestore.indexes.json            # composite indexes
.env.local                        # secrets (gitignored)
.env.example                      # var names only, no values
```

---

## 9. Rules for agents

1. **Stay in scope.** If a request touches §2 "Out of scope," stop and flag it.
2. **JavaScript only.** No TypeScript files and no new languages. (The `main.py` and `.venv` in the repo root are IDE leftovers and not part of the app.)
3. **No secrets in code or commits.** Read keys from `process.env`. Add any new var to `.env.example`. Never commit a Firebase service-account JSON file.
4. **External APIs are called only on the server**, inside `lib/` and through route handlers, and always through the cache.
5. **Use the shared data model (§5) and API contract (§7).** If you must change them, update this file in the same change.
6. **Use `lib/dateWindow.js`** for the 4-year window everywhere. Don't recompute it ad hoc.
7. **Neutral, factual UI copy.** Show official vote data as-is.
8. **Fail gracefully.** If news or AI is down, the vote data still renders.
9. **Keep changes small and focused**, one feature per branch/PR. Don't refactor teammates' areas without asking.
10. **Don't add heavy dependencies** without noting why in the PR.
11. **Test the parsers** (`lib/senate`, ID mapping, policyId normalization) with saved sample XML/JSON fixtures, not live calls.

---

## 10. Open decisions (team to fill in)

| Decision | Options | Decided |
|---|---|---|
| News provider | NewsAPI.org / GNews / Guardian | _TBD_ |
| Database | Cloud Firestore | **Decided** |
| AI model | DeepSeek (`deepseek-r1`) via Ollama | **Decided**. Size tag (8b/14b) TBD by hardware |
| Styling | Tailwind / CSS Modules | _TBD_ |
| Ingest strategy | Pre-ingest via script / fetch-on-demand + cache | _TBD_ |

---

## 11. Environment variables

```
CONGRESS_API_KEY=
NEWS_API_KEY=
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:8b

# Firebase Admin (from a service account; server only, never NEXT_PUBLIC_)
FIREBASE_PROJECT_ID=
FIREBASE_CLIENT_EMAIL=
FIREBASE_PRIVATE_KEY=   # keep the \n escapes; replace them with real newlines in code
```
