"use client";
import Image from "next/image";
import { useState } from "react";
import { externalHref } from "@/lib/display";

export default function Portrait({ member }) {
  const [failedUrl, setFailedUrl] = useState(null);
  const url = externalHref(member.photoUrl);
  const initials = member.name.split(/\s+/).filter(Boolean).slice(0, 2).map(name => name[0]).join("");
  return <span className="portrait" aria-hidden="true">
    {url && failedUrl !== url ? <Image unoptimized src={url} width={96} height={96} alt="" onError={() => setFailedUrl(url)} /> : initials}
  </span>;
}
