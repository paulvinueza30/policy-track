import SignIn from "@/components/SignIn";
export const dynamic = "force-dynamic";
export default function SignInPage(){return <main className="frame page"><SignIn clientId={process.env.GOOGLE_CLIENT_ID || ""} /></main>;}
