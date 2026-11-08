# RealNew frontend

The Next.js app reads congressional data from Policy Track’s FastAPI backend. Set `NEXT_PUBLIC_API_URL` in `.env.local` to the backend origin, without the `/api` suffix. Keep Firebase, news, and DeepSeek credentials in the backend environment.

## Run locally

Start FastAPI from the `backend` directory in this checkout. Follow the root README for Firestore setup and congressional data ingest. Verify the backend at [localhost:8000/docs](http://localhost:8000/docs).

From the frontend directory, copy `.env.example` to `.env.local`, then run:

```sh
npm ci
npm run dev
```

Open the local URL printed by Next.js. Select a state, switch between Senators and House Reps, open a member dossier, and follow a roll call to its details. A roll call with an associated policy also offers related news and an AI summary. The summary requires an implemented DeepSeek endpoint. News or summary outages leave the available vote data visible.

`npm run lint` checks the source and `npm run build` creates a production build.

District boundaries are bundled Census maps for the 119th Congress; see public/maps/districts/README.md to regenerate them. Portraits use photoUrl from FastAPI with initials as fallback. The frontend does not invent missing records or summaries.
