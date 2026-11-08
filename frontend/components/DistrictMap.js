"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { districtLabel, ordinal, stateHref } from "@/lib/display";

export default function DistrictMap({ state, district, members = [] }) {
  const router = useRouter();
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [tooltip, setTooltip] = useState(null);
  useEffect(() => {
    const abort = new AbortController();
    fetch("/maps/districts/" + state.code + ".json", { signal: abort.signal })
      .then(response => { if (!response.ok) throw new Error("Map unavailable"); return response.json(); })
      .then(setData).catch(error => { if (error.name !== "AbortError") setError(true); });
    return () => abort.abort();
  }, [state.code]);
  const numbers = data?.districts.map(item => item.district) ?? [...new Set(members.map(member => member.district).filter(n => n != null))].sort((a,b) => a-b);
  function locate(event, number) {
    const link = event.currentTarget.getBoundingClientRect();
    const map = event.currentTarget.ownerSVGElement.getBoundingClientRect();
    const member = members.find(m => m.district === number && !m.inOfficeTo);
    setTooltip({ text: districtLabel({state:state.code, district:number}) + (member ? " · " + member.name : ""),
      x: Math.max(100, Math.min(map.width - 100, link.left - map.left + link.width / 2)), y: Math.max(60, link.top - map.top) });
  }
  return <div className="map-panel district-panel">
    <p className="map-label"><span className="map-key" /><strong>{state.name}</strong> · Congressional districts</p>
    <div className="map-canvas">
      {!data && <p className="empty" role="status">{error ? "The district map is unavailable. Use the district selector below." : "Loading district boundaries…"}</p>}
      {data && <svg viewBox={data.viewBox} className="district-map" role="group" aria-label={state.name + " congressional districts"}>
        {data.districts.map(item => <Link key={item.district} href={stateHref(state.code, "house", item.district)} prefetch={false}
          aria-label={state.name + " " + (item.district === 0 ? "At-large" : ordinal(item.district)) + " Congressional District"}
          aria-current={district === item.district ? "true" : undefined}
          onPointerEnter={event => { if (event.pointerType === "mouse") locate(event, item.district); }}
          onPointerLeave={() => setTooltip(null)} onFocus={event => locate(event, item.district)} onBlur={() => setTooltip(null)}>
          <path d={item.path} fillRule="evenodd" />
        </Link>)}
      </svg>}
      {tooltip && <div className="map-tooltip" aria-hidden="true" style={{left:tooltip.x,top:tooltip.y}}><strong>{tooltip.text}</strong></div>}
    </div>
    <label className="district-selector">Congressional district
      <select value={district ?? ""} onChange={event => router.push(stateHref(state.code, "house", event.target.value === "" ? null : Number(event.target.value)))}>
        <option value="">Select a district</option>
        {numbers.map(number => <option key={number} value={number}>{districtLabel({state:state.code,district:number})}</option>)}
      </select>
    </label>
    <p className="map-note">District lines shown for the current Congress (119th). Former members may have represented a different area.</p>
    <a className="district-help" href="https://www.house.gov/representatives/find-your-representative" target="_blank" rel="noreferrer">Find your district on house.gov ↗</a>
  </div>;
}
