"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { sessionRequest } from "@/lib/api";
import { resetFollowing } from "@/lib/following";

export default function DeleteAccount() {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const cancel = useRef(null);
  const start = useRef(null);
  const wasConfirming = useRef(false);

  useEffect(() => {
    if (confirming) cancel.current?.focus();
    else if (wasConfirming.current) start.current?.focus();
    wasConfirming.current = confirming;
  }, [confirming]);

  async function remove() {
    setBusy(true);
    setError("");
    try {
      await sessionRequest("delete", {});
      resetFollowing();
      router.replace("/");
      router.refresh();
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  return (
    <section className="panel delete-account" aria-labelledby="delete-title">
      <h2 id="delete-title">Your data</h2>
      {!confirming && <button type="button" ref={start} className="danger-button" onClick={() => setConfirming(true)}>Delete my data</button>}
      {confirming && (
        <div role="group" aria-label="Confirm deleting your data" onKeyDown={(e) => { if (e.key === "Escape" && !busy) setConfirming(false); }}>
          <p>This permanently deletes your saved district, followed lawmakers and reactions, and signs you out. It can’t be undone.</p>
          <div className="personal-actions">
            <button type="button" ref={cancel} className="button" disabled={busy} onClick={() => setConfirming(false)}>Cancel</button>
            <button type="button" className="danger-button" disabled={busy} onClick={remove}>{busy ? "Deleting…" : "Yes, delete my data"}</button>
          </div>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
