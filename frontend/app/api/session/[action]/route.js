import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { accountRequest, ApiError } from "@/lib/api";

const cookieName = "realnews_session";
const MAX_SESSION_SECONDS = 30 * 24 * 60 * 60;
const NEWS_TIMEOUT_MS = 30_000; // the first request can gather news for every followed lawmaker
export async function GET(request, { params }) {
  const { action } = await params;
  const token = (await cookies()).get(cookieName)?.value;
  if (!token) return NextResponse.json({error:{message:"Sign in to continue"}}, {status:401});
  try {
    const suffix = action === "me" ? "" : action === "feed" ? "/feed" + new URL(request.url).search : action === "news" ? "/news" : null;
    if (suffix === null) return NextResponse.json({error:{message:"Not found"}},{status:404});
    const data = await accountRequest(suffix, {headers:{Authorization:"Bearer " + token}}, action === "news" ? NEWS_TIMEOUT_MS : undefined);
    return NextResponse.json(data, {headers:{"Cache-Control":"no-store"}});
  } catch(error) { return failure(error); }
}
export async function POST(request, { params }) {
  // Same-origin JSON requests only; prevents login CSRF and preference changes from other sites.
  if (request.headers.get("origin") !== new URL(request.url).origin || !request.headers.get("content-type")?.includes("application/json")) {
    return NextResponse.json({error:{message:"Invalid request origin"}},{status:403});
  }
  const {action} = await params;
  try {
    const jar = await cookies();
    if (action === "logout") {
      // End the session on the server first, then always clear the cookie so this browser signs out.
      const token = jar.get(cookieName)?.value;
      let revoked = false;
      if (token) {
        try {
          await accountRequest("/sign-out", {method:"POST",headers:{Authorization:"Bearer " + token}});
          revoked = true;
        } catch (error) {
          if (!(error instanceof ApiError)) throw error;
        }
      }
      jar.delete(cookieName);
      return NextResponse.json({ok:true,revoked});
    }
    const body = await request.json();
    if (action === "login") {
      if (typeof body.credential !== "string" || body.credential.length > 8192) return NextResponse.json({error:{message:"Invalid credential"}},{status:400});
      // The token stays in the HttpOnly cookie and is never sent to the browser.
      const session = await accountRequest("/session", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({credential:body.credential})});
      const user = await accountRequest("", {headers:{Authorization:"Bearer " + session.token}});
      jar.set(cookieName, session.token, {httpOnly:true, secure:new URL(request.url).protocol === "https:", sameSite:"lax", path:"/", maxAge:Math.max(0, Math.min(MAX_SESSION_SECONDS, session.expiresAt - Math.floor(Date.now()/1000)))});
      return NextResponse.json(user);
    }
    if (!["preferences", "follow", "unfollow", "delete"].includes(action)) return NextResponse.json({error:{message:"Not found"}},{status:404});
    const token = jar.get(cookieName)?.value;
    if (!token) return NextResponse.json({error:{message:"Sign in to continue"}},{status:401});
    const auth = {Authorization:"Bearer " + token};
    if (action === "preferences") {
      // Follows change only through the follow routes, so a stale tab can't overwrite them.
      const preferences = {...body};
      delete preferences.following;
      return NextResponse.json(await accountRequest("/preferences",{method:"PUT",headers:{...auth,"Content-Type":"application/json"},body:JSON.stringify(preferences)}));
    }
    if (action === "delete") {
      await accountRequest("",{method:"DELETE",headers:auth});
      jar.delete(cookieName);
      return NextResponse.json({ok:true});
    }
    if (typeof body.bioguideId !== "string" || !/^[A-Z]\d{6}$/i.test(body.bioguideId)) return NextResponse.json({error:{message:"Invalid member"}},{status:400});
    return NextResponse.json(await accountRequest("/following/" + encodeURIComponent(body.bioguideId.toUpperCase()),{method:action === "follow" ? "PUT" : "DELETE",headers:auth}));
  } catch(error) { return failure(error); }
}
function failure(error) {
  return NextResponse.json({error:{message:error instanceof ApiError ? error.message : "Account service unavailable"}},{status:error instanceof ApiError ? error.status || 503 : 503,headers:{"Cache-Control":"no-store"}});
}
