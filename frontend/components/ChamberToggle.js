import Link from "next/link";
import { stateHref } from "@/lib/display";
export default function ChamberToggle({ stateCode, chamber }) {
  return <nav className="segments chamber-toggle" aria-label="Chamber">
    <Link href={stateHref(stateCode, "senate")} aria-current={chamber === "senate" ? "page" : undefined}>Senators</Link>
    <Link href={stateHref(stateCode, "house")} aria-current={chamber === "house" ? "page" : undefined}>House Reps</Link>
  </nav>;
}
