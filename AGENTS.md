# Agent Guide: VoteLens, a U.S. Congress Vote Tracker

Read this first. It is the source of truth for project scope. If a task isn't covered here or goes against it, stop and ask a human teammate instead of guessing. When the team changes a decision, update this file in the same change.

> **Status: the House of Representatives is newly in scope.** The House backend is built on the `backend-(dhyan)` branch. The frontend still needs to move to it (§12); until then the old `/api/senators` routes keep working. Older branches still read the legacy `senators` collection, so don't delete it until everyone has moved over.

---

## 1. What we are building

A web app where a user picks a **U.S. state** and sees:

1. That state's **members of Congress**: its 2 **U.S. Senators** and its **U.S. Representatives** by district (current, plus anyone who held the seat in the time window).
2. The **roll-call votes** each member cast in the **last 4 years**, in the Senate or the House, and the bill, resolution or nomination each vote was on.
3. **News articles** about each policy or bill.
4. An **AI summary** of each policy, made by **DeepSeek running on our private server**, that explains what the policy does and how the state's members voted.

### Target user
A regular person who wants to know, without spin, how their senators and representative voted.

### Definition of done (MVP)
- [ ] State picker (all 50 states) → state page with a **Senators / House Reps** toggle; the House view shows a clickable map of the state's congressional districts
- [ ] Member page → list of their votes (newest first), filterable by date range and by vote position (Yea / Nay / Not Voting / Present), and by chamber if they served in both
- [ ] Policy/vote detail page → official info (title, date, chamber, result, tally), how the selected state's members voted, related articles, AI summary
- [ ] A policy voted on by both chambers shows its Senate and House votes on one page
- [ ] AI summary shows the sources it used and can be regenerated
- [ ] Works locally: frontend with `npm run dev`, backend with `uvicorn app.main:app --reload`, and network access to the DeepSeek server

---

## 2. Scope

### In scope
- **U.S. Senate and U.S. House of Representatives**, all 50 states
- Voting members only: 100 senators and 435 representatives, including former members who served during the window
- **Rolling 4-year window**: from today minus 4 years to today. Compute it at runtime. Never hardcode dates. As of Nov 2026 this covers part of the 117th Congress (2nd session, 2022), the 118th (2023–2024) and the 119th (2025–2026).
- Recorded roll-call votes on bills, resolutions, amendments and nominations (nominations are Senate-only), plus procedural votes
- A clickable congressional district map for each state (§4.5, §12)
- News articles linked to a policy
- AI summaries and Q&A about a single policy, using our self-hosted DeepSeek

### Out of scope. Do not build these unless the team updates this file.
- State legislatures, governors
- Non-voting House delegates and the Resident Commissioner (DC, PR, GU, VI, AS, MP) as members. They aren't listed, but they do count in the official tally on some amendment votes (Committee of the Whole), so a vote's tally can be up to 6 higher than the members listed
- Elections of the Speaker (20 roll calls in the window). Members vote for a person, not Yea/Nay, so these don't fit the vote model. The ingest skips them
- Voice votes and other votes with no recorded individual positions
- ZIP-code-to-district lookup (the UI links to house.gov instead; see §12)
- Maps of past district boundaries (the map shows the current Congress only)
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
                                                                         ├──> senate.gov XML + House Clerk XML (Voteview as fallback)
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
| XML parsing | `lxml` or the standard-library `xml.etree.ElementTree` | For senate.gov and House Clerk vote files |
| Database/cache | **Cloud Firestore** via the Python `firebase-admin` SDK | See §5.1 |
| AI | **DeepSeek** on our **private server** | See §6 |
| Backend testing | Manual, through FastAPI's interactive docs at `/docs` | No automated test suite |
| Styling | Team's choice (Tailwind recommended) | Keep it consistent once picked |

**The frontend only ever talks to the FastAPI backend.** Secrets (API keys, Firebase credentials, DeepSeek URL/key) live only in the backend.

---

## 4. Data sources (all called from the backend)

### 4.1 Congress.gov API (bills, members, summaries)
- Base URL: `https://api.congress.gov/v3`. Free key from https://api.data.gov/signup. Env var `CONGRESS_API_KEY`.
- Rate limit: about 5,000 requests per hour. **Cache responses**, and never re-fetch the same bill on every page load.
- Useful endpoints:
  - `GET /member/congress/{congress}/{stateCode}` returns members by state (both chambers)
  - `GET /member/{bioguideId}` returns member details
  - `GET /bill/{congress}/{billType}/{billNumber}` returns bill details
  - `GET /bill/{congress}/{billType}/{billNumber}/summaries` returns CRS summaries (**main AI grounding text**)
  - `GET /bill/{congress}/{billType}/{billNumber}/actions`
- **Important:** do not use Congress.gov for votes. It has no Senate roll-call votes. Its `house-vote` endpoint is in beta and starts at the 118th Congress, so it doesn't cover the full window. Use 4.2 and 4.2a.

### 4.2 Senate.gov roll-call vote XML (the votes)
- Vote list per session:
  `https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_{congress}_{session}.xml`
- Single vote detail, with each senator's position:
  `https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{session}/vote_{congress}_{session}_{voteNumber5digits}.xml`
  (example: `vote_119_1_00042.xml`)
- In these files, senators are identified by **`lis_member_id`** (like `S354`), **not** bioguide ID.
- No API key is needed. Be polite: throttle requests and cache aggressively. Past votes never change.
- **senate.gov often blocks automated requests (HTTP 403).** The ingest tries senate.gov first and, if blocked, falls back to Voteview for that session (4.2b). Do not try to get around the block (no fake browser user agents).

### 4.2a House Clerk roll-call XML (the House votes)
- One file per vote, by calendar year: `https://clerk.house.gov/evs/{year}/roll{voteNumber3digits}.xml` (example: `https://clerk.house.gov/evs/2025/roll042.xml`). There is no XML index, so count up from `roll001` until a 404.
- Members are in `<recorded-vote>`: `<legislator name-id="A000370" state="NC" party="D">` and `<vote>`. **`name-id` is the bioguide ID**, so no ID mapping is needed.
- `<vote>` can be `Yea`, `Nay`, **`Aye`, `No`**, `Present` or `Not Voting`. Normalize `Aye` to `Yea` and `No` to `Nay`.
- Useful fields: `<congress>`, `<session>` (`1st`/`2nd`), `<rollcall-num>`, `<legis-num>` (`H R 35`), `<vote-question>`, `<vote-result>`, `<action-date>` (`13-Feb-2025`), `<action-time time-etz="10:45">`.
- `<vote-desc>` is often the bill's popular name (`Agent Raul Gonzalez Officer Safety Act`). Use it as the vote `title`.
- Skip `Election of the Speaker` votes and quorum calls (`<vote-type>QUORUM</vote-type>`) (§2). No API key needed. Throttle requests; past votes never change.
- If the Clerk site is blocked or down, fall back to Voteview for that session, the same way as the Senate.

### 4.2b Voteview (fallback for votes)
- UCLA's public roll-call dataset, built from official congressional records. No key needed. Files per Congress and chamber (`S` or `H`):
  `https://voteview.com/static/data/out/{rollcalls|votes|members}/{S|H}{congress}_{kind}.csv`
- `clerk_rollnumber` is the official vote number, so vote IDs match the official sources (`s-119-1-00042`, `h-119-1-00042`).
- House `members` files include delegates. Keep them when counting tallies, but the ingest doesn't list them as members.
- Cast codes: 1 = Yea, 6 = Nay, 7/8 = Present, 2–5 and 9 = Not Voting (paired/announced votes are not cast votes), 0 = not a member.
- `members` CSV has `bioguide_id`, so no LIS mapping is needed. Voteview has no time of day; dates are stored as noon US Eastern.
- Code: `backend/app/services/voteview/`.

### 4.3 Members and ID mapping (LIS ↔ Bioguide)
- Use the public `unitedstates/congress-legislators` dataset (`legislators-current` and `legislators-historical`, JSON or YAML). It includes `id.lis`, `id.bioguide` and term info (`type: sen|rep`, `state`, `district`), and it also covers members who left office during the window.
- **Canonical member ID in our app = `bioguideId`.** Convert senate.gov LIS IDs during ingest.
- **One person can serve in both chambers during the window** (for example Adam Schiff, Ruben Gallego, Andy Kim and Elissa Slotkin moved from the House to the Senate). They are one `Member` with one vote history, and each role is listed in `roles`.

### 4.4 News articles
- Provider: **GNews** (`https://gnews.io/api/v4/search`, free tier 100 requests/day), behind one adapter in `backend/app/services/news/` so it can be swapped.
- Env var `NEWS_API_KEY`. The query is the short title, the nominee's name for nominations, or the bill number (e.g. `"S. 316" Congress`) when the title is a long official one.
- Store only the title, source, URL, published date and short description. **Do not scrape or store full article text.** Link out to the publisher.

### 4.5 Congressional district boundaries (map shapes)
- Source: U.S. Census Bureau cartographic boundary files, public domain: `https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_500k.zip` (119th Congress). Keep only the 50 states; each district is identified by its state FIPS code and `CD119FP` (`00` = at-large).
- **These are static files, not an API call.** A one-time script (`frontend/scripts/build-district-maps.mjs`) converts them to per-state SVG path files in `frontend/public/maps/districts/{STATE}.json`. Commit the output. Simplify the shapes so each state's file stays small (aim for under 150 KB).
- This is the one exception to rule 4: map shapes are bundled with the frontend, because they aren't member or vote data and never change during a Congress.
- **Regenerate when a new Congress starts** (the 120th begins January 2027, and several states have redrawn their maps). TIGERweb's Legislative service already lists a 120th Congress layer.

### 4.6 Member photos (backend URLs, frontend portraits with initials fallback)
- **Yes, photos can come from an API.** The backend saves one URL per member in `photoUrl` during ingest, and the API already returns it. The frontend never calls a photo service itself.
- **Primary source:** `https://unitedstates.github.io/images/congress/225x275/{bioguideId}.jpg`. No key needed. Public-domain official portraits. Works from our network. Checked November 2026: 518 of 533 current members and 165 of 174 former members in the window have a photo.
- **Second source:** Congress.gov `GET /member/{bioguideId}` returns `depiction.imageUrl`. The ingest uses it to fill the gaps when Congress.gov responds. It sometimes hangs, so the ingest checks it once and skips it for that run if it doesn't answer.
- A missing photo is normal (new members usually), so `photoUrl` can be `null`. The UI always falls back to initials.

### Linking a vote to a policy
Senate vote XML has a `<document>` block (e.g. `S. 870`, `H.R. 2`, `PN 123`). House vote XML has `<legis-num>` (e.g. `H R 35`, `H RES 5`, `S 870`). Normalize both to our `policyId` format: `{congress}-{billType}-{number}` (e.g. `118-hr-2`). Nomination votes use `{congress}-pn-{number}`.

**The same bill keeps the same `policyId` in both chambers**, so `118-hr-2` collects its House and Senate votes on one policy page. Some votes (motions, quorum-related votes) have no document. Show them, but skip articles and AI for them.

---

## 5. Core data model

These are the shared contract between frontend and backend, so don't rename fields without updating this file. Define each one as a Pydantic model in `backend/app/models/`.

**Field names in JSON are camelCase** (as below), even though Python code uses snake_case. Use a Pydantic alias generator (`alias_generator=to_camel`, `populate_by_name=True`) and return responses by alias.

```js
// Member (senator or representative)
{ bioguideId, lisId /* senators only */, name, party, state,
  chamber /* "senate" | "house": current or most recent */,
  district /* number; 0 = at-large; null for senators */,
  inOfficeFrom, inOfficeTo /* null if current */, photoUrl /* nullable; see §4.6 */,
  roles: [{ chamber, state, district, party, from, to /* null if current */ }] /* every role in the window */ }

// Vote (one roll call in either chamber)
{ voteId /* "s-119-1-00042" or "h-119-1-00042" */, chamber /* "senate" | "house" */, congress, session, voteNumber,
  date, question, result, policyId /* nullable */, tally: { yea, nay, present, notVoting },
  title /* what it's about: bill title or nominee; nullable */, documentLabel /* "H.R. 6938" or "PN 373"; nullable */ }

// MemberVote (name, party, state, district are optional display fields)
{ voteId, bioguideId, position /* "Yea" | "Nay" | "Present" | "Not Voting" */, name, party, state, district }

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
| `members` | `bioguideId` | `Member` |
| `members/{bioguideId}/votes` | `voteId` | `Vote` fields copied in + `position` (lets the member page load with one query) |
| `votes` | `voteId` | `Vote` + `positions: { [bioguideId]: position }` + `members: MemberVote[]` |
| `policies` | `policyId` | `Policy` + `articlesFetchedAt` |
| `policies/{policyId}/articles` | hash of the article URL | `Article` + `fetchedAt` |
| `aiSummaries` | `{policyId}__{model}` (`:` and `/` in the model name become `_`) | `AiSummary` |
| `meta` | e.g. `ingest` | last ingested vote per chamber/congress/session, used for incremental updates |

Rules:
- **Only the backend talks to Firestore**, using the Python `firebase-admin` SDK in `backend/app/db/`. Set the security rules to deny all client reads and writes.
- Store fields in camelCase, matching §5.
- Store dates as Firestore `Timestamp`s (Python `datetime` with a timezone) so queries can filter and sort by date.
- Vote lists sort by `date desc, voteNumber desc` and need the **composite indexes** in `firestore.indexes.json` (deploy them with `firebase deploy --only firestore:indexes`). Adding the `chamber` filter needs new indexes for `chamber` + `date` and `chamber` + `position` + `date`, both for sorting and for counting.
- All Firestore code lives in `backend/app/db/repository.py`. Routers get it through the `get_repo` dependency, which returns `503` if Firebase isn't configured.
- Use **batched writes** (max 500 operations per batch) during ingest.
- Keep reads low and never read a whole collection on a request. Member vote pages use `offset()` + `limit()` so the API can take a page number (at most ~2,000 votes per member, so the skipped reads stay small).
- **Write cost:** each Senate vote is ~101 writes and each House vote is ~436 (the vote + one copy per member). A full 4-year load is about 270,000 Senate writes plus 860,000 House writes (1,981 votes), or **roughly 1.1 million writes**. The free Spark plan allows 20,000 writes/day, so **the full load needs the Blaze plan** (about $2). Test with `--limit`.
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
- **Grounding:** the prompt may only use our data, meaning the CRS summary, bill title and actions, vote result and tally, how the state's members voted in each chamber, and article titles and descriptions. Tell the model to answer only from the provided context and to say "not enough information" otherwise.
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
| `GET /api/states/{stateCode}/members?chamber=` | `Member[]` for that state in the window. Senators first, then representatives by district. `chamber` (`senate` or `house`) is optional. **With `chamber`, each member's `chamber`, `district`, `party` and in-office dates describe their service in that chamber**, so Adam Schiff with `chamber=house` is CA-30 and shows as former |
| `GET /api/members/{bioguideId}` | `Member` |
| `GET /api/members/{bioguideId}/votes?chamber=&from=&to=&position=&page=&pageSize=` | `{ items: (Vote & { position })[], page, pageSize, total }`. Dates are `YYYY-MM-DD`, clamped to the window; `pageSize` defaults to 25, max 100 |
| `GET /api/votes/{voteId}` | `Vote` + `memberVotes: MemberVote[]` (sorted by state, then district, then name). `senatorVotes` is a temporary copy for the current frontend |
| `GET /api/policies/{policyId}` | `Policy` + `votes: Vote[]` from both chambers (newest first) |
| `GET /api/policies/{policyId}/articles` | `Article[]`, newest first. Cached 24 h; stale cache is served if GNews fails, otherwise `503` |
| `POST /api/ai/summary` body `{ policyId, stateCode?, regenerate? }` | `AiSummary` |

**Migration:** keep `/api/states/{code}/senators` and `/api/senators/...` (already built) working as thin aliases for Senate members until the frontend has moved to the routes above, then delete them.

The frontend reads the backend URL from `NEXT_PUBLIC_API_URL` and keeps all fetch calls in `frontend/lib/api.js`.

---

## 8. Project structure

```
/frontend                         # Next.js app (JavaScript)
  /app
    page.js                       # home: state picker
    /state/[stateCode]/page.js    # Senate and House views
    /member/[bioguideId]/page.js  # replaces /senator/[bioguideId]
    /vote/[voteId]/page.js
    /policy/[policyId]/page.js
  /components                     # React UI components
  /lib/api.js                     # the only place that calls the backend
  /public/maps/districts/         # generated per-state district shapes ({STATE}.json)
  /scripts/build-district-maps.mjs  # one-time generator for the district shapes
  package.json
  .env.example

/backend                          # FastAPI app (Python)
  /app
    main.py                       # FastAPI app, CORS, error handlers, routers
    config.py                     # env settings (pydantic-settings)
    deps.py                       # FastAPI dependencies (get_repo, get_http)
    date_window.py                # single source for the 4-year window
    states.py                     # the 50 state codes
    /routers/                     # one file per resource (states, members, votes, policies, ai)
    /models/                      # Pydantic models from §5
    /services/
      http.py                     # shared httpx client (User-Agent, timeouts)
      vote_types.py               # source-neutral ParsedVote + policyId helpers
      /congress/                  # Congress.gov client
      /senate/                    # senate.gov XML fetch + parse
      /house/                     # House Clerk XML fetch + parse
      /voteview/                  # Voteview CSV fallback
      /legislators/               # members in window + LIS <-> bioguide mapping
      /news/                      # GNews adapter
      /ai/                        # DeepSeek client + prompt builders (AI teammate)
    /db/
      __init__.py                 # firebase-admin init (async Firestore client)
      repository.py               # every Firestore read/write
  /scripts/ingest.py              # pulls members, votes, policies into Firestore (see --help)
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
4. **Only the backend calls external services** at runtime (Congress.gov, senate.gov, clerk.house.gov, Voteview, news, Firestore, DeepSeek), and always through the cache. The frontend calls only our FastAPI API, through `frontend/lib/api.js`.
5. **Only `NEXT_PUBLIC_API_URL` may be exposed to the browser.** Never put a secret in a `NEXT_PUBLIC_` variable.
6. **Use the shared data model (§5) and API contract (§7).** If you must change them, update this file and both sides (Pydantic model and frontend usage) in the same change.
7. **Use `backend/app/date_window.py`** for the 4-year window everywhere. Don't recompute it ad hoc.
8. **Neutral, factual UI copy.** Show official vote data as-is.
9. **Fail gracefully.** If news or AI is down, the vote data still renders.
10. **Keep changes small and focused**, one feature per branch/PR. Frontend and backend work can go in separate PRs, as long as the contract in §7 is respected. Don't refactor teammates' areas without asking.
11. **Python style:** type hints everywhere, `async` route handlers and `httpx.AsyncClient`, format with `ruff` (or `black`). Pin dependencies in `requirements.txt`.
12. **Don't add heavy dependencies** without noting why in the PR.
13. **Test manually in the FastAPI UI.** Run `uvicorn app.main:app --reload` and try each endpoint at http://localhost:8000/docs. Use `python -m scripts.ingest --dry-run --limit 3` to check the data sources without writing to Firestore. Don't add an automated test suite unless the team decides to.
14. **Vote labels are two lines:** `title` (what it's about), then the plain-English vote type from `voteSubtitle()` in `frontend/lib/display.js` (mapping in §12). Keep the vote type visible, because a Yea on a procedural vote doesn't necessarily mean support for the measure.
15. **Use chamber-neutral code and accurate titles.** Say "member" in code and shared UI. Say "Senator" or "Representative" only when the chamber is known. Never assume a vote or member is in the Senate.

---

## 10. Open decisions (team to fill in)

| Decision | Options | Decided |
|---|---|---|
| Backend | FastAPI (Python) | **Decided** |
| Database | Cloud Firestore | **Decided** |
| AI model | DeepSeek on our private server | **Decided**. Serving stack (vLLM / Ollama / other) and exact model TBD |
| News provider | GNews | **Decided** |
| Senate vote source | senate.gov XML, falling back to Voteview when blocked | **Decided** |
| House vote source | House Clerk XML, falling back to Voteview | **Decided** |
| House scope details | Voting members of the 50 states only; skip Speaker elections; no ZIP lookup | **Proposed**, confirm with team |
| District map | Clickable per-state map from Census boundary files, current Congress only | **Decided** |
| Member photos | Use backend `photoUrl`, with initials fallback | **Decided** |
| Data model for both chambers | One `members` collection and `Member` model; `s-`/`h-` vote ID prefixes | **Built**, confirm with team |
| Firebase plan | Blaze required for the full load (about $2) | _TBD_, Firebase owner |
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

---

## 12. Frontend UI spec: Senate + House

**Audience: the frontend developer.** Keep the existing VoteLens visual design (panels, typography, badges, the map, `VoteCard`, the two-line vote labels). This is a change to content and navigation, not a redesign. Work in `frontend/` only and use the routes in §7.

### 12.1 Site-wide copy

| Where | New text |
|---|---|
| Browser title (`layout.js`) | `VoteLens \| U.S. Congress Vote Tracker` |
| Header tagline | `U.S. Congress votes in plain English` |
| Home heading | `Understand how your members of Congress vote on what matters to you.` |
| Home intro | `Explore your state's senators and representatives, browse roll-call votes, and see policy explained in plain English.` |
| Breadcrumb root (replaces "United States Senate") | `U.S. Congress` |
| Footer | `A Policy Track project for exploring the U.S. Congress.` |

Member labels: `Senator` / `Representative`, `Current senator` / `Former senator`, `Current representative` / `Former representative`. District labels: `WA-7 · 7th District`, or `WY · At-large` when the district is 0.

### 12.2 Pages

**Home (`/`)**: same map and state picker. Rename `SenateMap` to `StateMap`. Heading: `Explore by state`. Sub-text: `Select a state to see its senators and representatives.` Remove the "2 U.S. Senators per state" tag and the map's "2 U.S. Senators" text. The toggle isn't shown here. Clicking a state opens the state page.

**State page (`/state/[stateCode]?chamber=senate|house&district=<number>&member=<bioguideId>`)**

After a state is clicked, the page opens with a **`Senators` / `House Reps`** toggle above the map. The default is `Senators`.

```
Washington
             [ Senators ] [ House Reps ]    <- toggle

Senators view                    House Reps view
[ U.S. map, state highlighted ]  [ Zoomed map of the state's districts ]
[ State picker ]                 [ State picker ] [ District dropdown ]
Maria Cantwell ...               Find your district on house.gov ↗
Patty Murray ...                 WA-7 · 7th District
                                 Pramila Jayapal · Democrat · Current
                                 Former members of this district, if any
Selected member + "Open member profile →"
Voting Record: <member>   (3 most recent votes)
```

Toggle:
- Use links that update `?chamber=` so views can be shared and the back button works, with `aria-current` on the active option. Keep the state when switching.
- Switching to `House Reps` replaces the national map with that state's district map. Switching back restores the national map.

District map (`DistrictMap` component):
- Load `/maps/districts/{STATE}.json` only when the House view opens, and show a loading state in the map area. The file shape is `{ "viewBox": "...", "districts": [{ "district": 7, "path": "M..." }] }`.
- Every district is clickable and sets `?district=`. Reuse the national map's hover and focus tooltip, showing `WA-7 · Pramila Jayapal`. Highlight the selected district the same way the selected state is highlighted.
- Selecting a district updates the panel and the `Voting Record` below it to that district's representative. With no district selected, prompt: `Select a district on the map.`
- Don't color districts by party or by any vote result. The map only shows location and selection.
- Each district must be a keyboard-focusable link with `aria-label="Washington 7th Congressional District"`.
- **Always include the district dropdown.** Dense city districts (New York, Los Angeles, Chicago) are too small to tap on a phone. The dropdown also serves screen-reader users.
- At-large states (AK, DE, ND, SD, VT, WY) have one shape. Select it automatically and label it `At-large`.
- Note under the map: `District lines shown for the current Congress. Former members may have represented a different area.`
- Link `Find your district on house.gov` to `https://www.house.gov/representatives/find-your-representative` and open it in a new tab. Many people don't know their district number.

Members list:
- Find the district's members by filtering the `getStateMembers(code, "house")` response on `district`. Show the current representative first, then former members.
- If the selected `member` isn't in the active view, fall back to the first senator or the selected district's current representative.
- A person who served in both chambers appears in each view with the matching role (use `roles`).

**Member page (`/member/[bioguideId]`)** replaces `/senator/[bioguideId]`. Make `/senator/[id]` redirect here.

- Eyebrow: `U.S. Senate · Washington` or `U.S. House · WA-7 · 7th District`. Heading is the name. Tags: party and current/former status.
- Section title: `Senate Votes`, `House Votes`, or `Votes in Congress` for someone who served in both.
- For members with both roles, add a `Chamber` filter (All / Senate / House) to the existing position and date filters, and a small chamber chip on each row. Show a short note listing their roles and dates.
- Keep "Three most recent / All votes" and pagination as they are.

**Vote page (`/vote/[voteId]`)**

- Eyebrow: `Senate roll call` or `House roll call`.
- The House has up to 435 rows, so don't render one long list. Heading: `How Members Voted`. Add filters for **State**, **Position** and **Party**. If the URL has `?state=`, start filtered to that state and show `How Washington Members Voted`.
- Group the rows by state when no state is selected. Each row: name, district label for the House, position badge.
- Vote numbers restart per chamber and session, so always show the chamber with `Roll call 42`.

**Policy page (`/policy/[policyId]`)**

- Replace `Roll Calls on This Policy` with `Votes in Congress`. List both chambers newest first, each row with a `Senate` or `House` chip, the question and the date. A policy with votes in only one chamber shows just that chamber.
- The selected roll call uses the same tally and `How Members Voted` layout as the vote page.
- When a state is selected, show that state's members grouped under `Senators` and `Representatives`, for the selected roll call only.
- Hide the bottom-of-page sections only if their data is missing. AI summary and news behave as they do now.

### 12.3 Shared components and code

| Now | Change |
|---|---|
| `SenateMap` | Rename `StateMap`; remove Senate-specific text |
| New `DistrictMap` | Per-state clickable district map (see §12.2); shares `StateMap`'s tooltip and selected styles |
| New `ChamberToggle` | The `Senators` / `House Reps` toggle |
| `Portrait({ senator })` | `Portrait({ member })`. Use API photo with initials fallback (§12.7) |
| `DelegationExplorer` | Use `ChamberToggle`; swap the map by chamber; props become `members`, `chamber`, `district` |
| `RollCall` | Use `memberVotes`; add filters and grouping for long lists |
| `VoteCard` and the All votes row | Show a `Senate`/`House` chip where the chamber isn't obvious from the page |
| `lib/api.js` | `getStateMembers(code, chamber)`, `getMember(id)`, `getMemberVotes(id, params)`; remove the senator functions after migration |
| `lib/display.js` | Add `chamberLabel()`, `districtLabel(member)`, `memberTitle(member)`; extend `VOTE_TYPES` |
| Error messages | Replace "Senate delegations" and "Senate data store" with chamber-neutral wording |

### 12.4 Plain-English House vote types

Add these to `VOTE_TYPES` in `lib/display.js`. **Order matters: test the specific patterns before the general ones.** Anything unmatched falls back to the official wording.

| Official wording contains | Show |
|---|---|
| `Suspend the Rules` | `Fast-track vote (needs two-thirds)` |
| `Objections of the President` | `Vote to override a veto` |
| `Previous Question` | `Vote to end debate and move to a vote` |
| `Motion to Recommit` or `Motion to Commit` | `Vote to send it back to committee` |
| `Motion to Refer` | `Vote to send it to a committee` |
| `Motion to Concur` | `Vote on the Senate's changes` |
| `Motion to Instruct` | `Vote to instruct negotiators` |
| `Motion to Adjourn` | `Vote to adjourn` |
| `Motion to Reconsider` | `Vote to reconsider` |
| `Consideration of the Resolution` | `Vote to start considering it` |
| `Agreeing to the Amendment` | `Vote on an amendment` |
| `Agreeing to the Resolution` or `On Passage` | `Vote to pass it` |

### 12.5 Requirements for every page

- **Neutral:** no scores, rankings or "good/bad" wording (§2). Show `Aye` and `No` votes as `Yea` and `Nay`; the backend normalizes them.
- **States:** loading, empty (`No House records are available for this state yet.`) and error states, with the rest of the page still working if one request fails.
- **Accessible:** tabs and filters work by keyboard, position is shown as text and not by color alone.
- **Responsive:** no sideways scrolling at 375px wide. The House list and vote tables must be usable on a phone.

### 12.6 Frontend done when

- [ ] Every Senate-only label is gone from shared pages
- [ ] Every state has a working `Senators` / `House Reps` toggle
- [ ] `/state/CA?chamber=house` shows a clickable map of all 52 districts, and clicking one shows its representative
- [ ] The district dropdown and the map stay in sync, and both work by keyboard and on a phone
- [ ] A member page works for a senator, a representative and someone who served in both
- [ ] `/senator/[id]` redirects to `/member/[id]`
- [ ] A House vote page is usable with 435 members on desktop and phone
- [ ] A bill voted on in both chambers shows both on its policy page

### 12.7 Member photos: API portraits with initials fallback

**Photos enabled by user request.** Render the API-provided `photoUrl` in `Portrait`, with initials for missing or failed images:

- Pass the whole `member` to `Portrait`, and keep the image area the same size and shape as the current initials circle so the layout won't move.
- The backend fills `member.photoUrl` (§4.6). `Portrait` then shows the image when `photoUrl` exists and falls back to initials when it's `null` or the image fails to load.
- Use `alt=""` when the name is already shown beside the photo, and add the photo host to `images.remotePatterns` in `next.config.mjs` if using `next/image`.
- Never build a photo URL or call a photo service in the frontend. Only use `photoUrl` from our API.
