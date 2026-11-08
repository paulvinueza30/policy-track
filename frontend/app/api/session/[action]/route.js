import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { accountRequest, ApiError } from "@/lib/api";

const cookieName = "realnews_session";
export async function GET(request, { params }) {
  const { action } = await params;
  const token = (await cookies()).get(cookieName)?.value;
  if (!token) return NextResponse.json({error:{message:"Sign in to continue"}}, {status:401});
  try {
    const suffix = action === "me" ? "" : action === "feed" ? "/feed" + new URL(request.url).search : null;
    if (suffix === null) return NextResponse.json({error:{message:"Not found"}},{status:404});
    const data = await accountRequest(suffix, {headers:{Authorization:"Bearer " + token}});
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
    if (action === "logout") { jar.delete(cookieName); return NextResponse.json({ok:true}); }
    const body = await request.json();
    if (action === "login") {
      if (typeof body.credential !== "string" || body.credential.length > 8192) return NextResponse.json({error:{message:"Invalid credential"}},{status:400});
      const user = await accountRequest("", {headers:{Authorization:"Bearer " + body.credential}});
      jar.set(cookieName, body.credential, {httpOnly:true, secure:new URL(request.url).protocol === "https:", sameSite:"lax", path:"/", maxAge:Math.max(0, Math.min(3600,user.expiresAt - Math.floor(Date.now()/1000)))});
      return NextResponse.json(user);
    }
    if (action !== "preferences") return NextResponse.json({error:{message:"Not found"}},{status:404});
    const token = jar.get(cookieName)?.value;
    if (!token) return NextResponse.json({error:{message:"Sign in to continue"}},{status:401});
    return NextResponse.json(await accountRequest("/preferences",{method:"PUT",headers:{Authorization:"Bearer " + token,"Content-Type":"application/json"},body:JSON.stringify(body)}));
  } catch(error) { return failure(error); }
}
function failure(error) {
  return NextResponse.json({error:{message:error instanceof ApiError ? error.message : "Account service unavailable"}},{status:error instanceof ApiError ? error.status || 503 : 503,headers:{"Cache-Control":"no-store"}});
}
