"use client";

import Link from "next/link";
import { useState } from "react";

export default function StateMap({ states, stateCode }) {
  const [hovered, setHovered] = useState(null);
  const [focused, setFocused] = useState(null);
  const tooltip = hovered ?? focused;
  const selected = states.find(({ code }) => code === stateCode);

  function locate(event, name) {
    const link = event.currentTarget.getBoundingClientRect();
    const map = event.currentTarget.ownerSVGElement.getBoundingClientRect();
    const x = link.left - map.left + link.width / 2;
    return {
      name,
      x: Math.max(88, Math.min(map.width - 88, x)),
      y: Math.max(52, link.top - map.top),
    };
  }

  return (
    <div className="map-panel">
      <p className="map-label">
        {selected ? <><span className="map-key" /> Selected state <strong>{selected.name}</strong></> : "Choose a state on the map"}
      </p>
      <div className="map-canvas">
        <svg viewBox="0 0 1020 630" className="senate-map" aria-label="Select a U.S. state" role="group">
          {states.map(({ code, name, path }) => (
            <Link key={code} href={"/state/" + code} prefetch={false} aria-label={name}
              aria-current={code === stateCode ? "true" : undefined}
              onPointerEnter={(event) => { if (event.pointerType === "mouse") setHovered(locate(event, name)); }}
              onPointerLeave={() => setHovered(null)}
              onFocus={(event) => setFocused(locate(event, name))}
              onBlur={() => setFocused(null)}>
              <path d={path} />
            </Link>
          ))}
        </svg>
        {tooltip && (
          <div className="map-tooltip" aria-hidden="true" style={{ left: tooltip.x, top: tooltip.y }}>
            <strong>{tooltip.name}</strong>
            <span>Explore members of Congress</span>
          </div>
        )}
      </div>
    </div>
  );
}
