# RealNews accounts and feed setup

1. Create a Google OAuth client of type **Web application** in your Google Cloud project. Configure the consent screen and authorized JavaScript origins (e.g. http://localhost:3000 and your HTTPS production origin).
2. Set the same public GOOGLE_CLIENT_ID in frontend/.env.local and backend/.env. Do not add a client secret to the browser. The Google button uses the callback flow, not a redirect URI.
3. Configure existing backend Firebase credentials. Keep Firestore client rules deny-all. Accounts are stored by verified Google subject; votes and members remain in existing collections. Deploy the existing vote indexes.
4. For automatic ZIP lookup obtain a HUD USPS Crosswalk API token and set HUD_API_KEY in backend/.env. Never expose this key. Manual state/district selection remains available without it. The crosswalk is pinned to 2025 Q4 / 119th Congress; update alongside the map vintage.
5. Start FastAPI and Next.js as usual. NEXT_PUBLIC_API_URL must point at FastAPI. Use matching hostname conventions (localhost vs 127.0.0.1) and HTTPS in production. Configure FRONTEND_ORIGIN appropriately.
6. Verify Google success, cancellation and expired sign-in, saved district after reload, follow/unfollow, reactions, feed pagination, split ZIP candidates and lookup outages. Configure actual client ID and Firebase before claiming end-to-end live sign-in success.

Google tokens stay in a one-hour HttpOnly cookie. Reauthentication is required after expiration; no refresh token or offline access is requested. Logout removes the local cookie. Private settings are not written to the browser's storage.

Feed scope: My district uses the selected representative and senators; National uses Congress-wide votes; Following uses up to 20 chosen lawmakers. The feed uses real roll calls and links to the existing policy pages for news and AI. It does not claim local-government coverage or personalize news using inferred political opinions. Reactions are private manual choices only.

References:
- https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- https://www.huduser.gov/portal/dataset/uspszip-api.html
