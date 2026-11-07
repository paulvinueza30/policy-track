# VoteLens frontend

The Next.js app reads Senate data from Policy Track’s FastAPI backend. Set `NEXT_PUBLIC_API_URL` in `.env.local` to the backend origin, without the `/api` suffix. Keep Firebase, news, and DeepSeek credentials in the backend environment.

## Run locally

Start the FastAPI backend first. The backend branch `backend-(dhyan)` has the delegation, roll-call, policy, and news endpoints. If those changes have yet to be merged into your checkout, run the backend from that branch in a separate checkout and follow its README for Firestore setup and Senate data ingest. Verify the backend at [localhost:8000/docs](http://localhost:8000/docs).

From the frontend directory, copy `.env.example` to `.env.local`, then run:

```sh
npm ci
npm run dev
```

Open the local URL printed by Next.js. Select a state, open a senator dossier, and follow a roll call to its details. A roll call with an associated policy also offers related news and an AI summary. The summary requires an implemented DeepSeek endpoint. News or summary outages leave the available vote data visible.

`npm run lint` checks the source and `npm run build` creates a production build.
