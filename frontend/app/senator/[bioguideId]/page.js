import { redirect } from "next/navigation";
export default async function SenatorRedirect({ params, searchParams }) {
  const { bioguideId } = await params;
  const query = new URLSearchParams(await searchParams);
  redirect("/member/" + encodeURIComponent(bioguideId) + (query.size ? "?" + query : ""));
}
