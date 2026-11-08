"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import FollowDelegation from "./FollowDelegation";
import states from "@/lib/states.json";
import { ApiError, getStateMembers, lookupZip } from "@/lib/api";
import { districtLabel, findState, stateHref } from "@/lib/display";

const NO_MATCHES = "No matching districts were found for this ZIP code. Choose your state below.";
const valueOf = (choice) => choice.state + ":" + choice.district;

function zipFailure(error) {
  if (!(error instanceof ApiError) || error.status === 0) return "ZIP search couldn’t be reached. Choose your state below.";
  if (error.status === 404) return NO_MATCHES;
  if (error.status === 422) return "Enter a valid 5-digit ZIP code.";
  return error.message;
}

/**
 * Finds a district by ZIP or state. The ZIP is only sent for the lookup and is never saved.
 * Signed in, `onSave(choice)` saves the confirmed district. Signed out, `onSelect(choice)` holds it for after sign-in.
 */
export default function DistrictLookup({ signedIn = false, selected, onSave, onSelect, onFollowed }) {
  const [zip, setZip] = useState("");
  const [state, setState] = useState("");
  const [choices, setChoices] = useState([]);
  const [source, setSource] = useState(null); // "zip" or "state"
  const [picked, setPicked] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(null);
  const latest = useRef(0);

  function reset() {
    latest.current += 1;
    setChoices([]);
    setSource(null);
    setPicked("");
    setError("");
    setBusy(false);
    setSaved(null);
    onSelect?.(null);
  }

  async function run(work, nextSource, failure) {
    const id = latest.current;
    setBusy(true);
    try {
      const found = await work();
      if (id !== latest.current) return;
      setChoices(found);
      setSource(nextSource);
      if (!found.length) setError(nextSource === "zip" ? NO_MATCHES : "No districts were found for this state.");
    } catch (e) {
      if (id === latest.current) setError(failure(e));
    } finally {
      if (id === latest.current) setBusy(false);
    }
  }

  function lookup(event) {
    event.preventDefault();
    reset();
    setState("");
    if (!/^\d{5}$/.test(zip)) {
      setError("Enter a 5-digit ZIP code.");
      return;
    }
    run(async () => {
      const result = await lookupZip(zip);
      return (result.districts ?? []).filter((choice) => findState(choice.state) && Number.isInteger(choice.district));
    }, "zip", zipFailure);
  }

  function chooseState(code) {
    reset();
    setZip("");
    setState(code);
    run(async () => {
      const members = await getStateMembers(code, "house");
      return [...new Set(members.map((m) => m.district).filter((d) => d != null))].sort((a, b) => a - b).map((district) => ({ state: code, district }));
    }, "state", (e) => e.message);
  }

  function pick(value) {
    setPicked(value);
    setSaved(null);
    setError("");
    onSelect?.(choices.find((choice) => valueOf(choice) === value) ?? null);
  }

  async function save() {
    const choice = choices.find((item) => valueOf(item) === picked);
    if (!choice || saving) return;
    setSaving(true);
    setError("");
    try {
      await onSave(choice);
      setSaved(choice);
    } catch (e) {
      setError(e.message || "Your district couldn’t be saved. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const choice = choices.find((item) => valueOf(item) === picked);
  const showingSaved = !choices.length && !saved && selected?.state;

  return (
    <section className="panel district-lookup">
      <p className="eyebrow">Your congressional district</p>
      <h2>Find your representation</h2>
      <p>A ZIP code can cross district lines. Confirm your district before saving.</p>
      {showingSaved && <p className="account-note">Your saved district: <strong>{districtLabel(selected)}</strong></p>}

      <form onSubmit={lookup} className="lookup-form" noValidate>
        <label htmlFor="residential-zip">5-digit ZIP code</label>
        <div className="picker-controls">
          <input id="residential-zip" inputMode="numeric" autoComplete="postal-code" maxLength={5} value={zip}
            onChange={(e) => { setZip(e.target.value.replace(/\D/g, "").slice(0, 5)); reset(); }} />
          <button className="button" type="submit" disabled={busy}>Look up</button>
        </div>
      </form>

      <label htmlFor="manual-state">Or choose your state</label>
      <select id="manual-state" value={state} disabled={busy} onChange={(e) => chooseState(e.target.value)}>
        <option value="" disabled>Select state</option>
        {states.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
      </select>

      {busy && <p role="status">Finding districts…</p>}
      {error && <p role="alert">{error}</p>}

      {source === "zip" && choices.length > 0 && (
        <fieldset className="zip-fieldset">
          <legend>Confirm your district</legend>
          {choices.map((item) => (
            <label key={valueOf(item)}>
              <input type="radio" name="district-confirm" value={valueOf(item)} checked={picked === valueOf(item)} onChange={() => pick(valueOf(item))} />
              {districtLabel(item)}
            </label>
          ))}
        </fieldset>
      )}

      {source === "state" && choices.length > 0 && (
        <div className="district-results">
          <label htmlFor="district-confirm">Confirm your district</label>
          <select id="district-confirm" value={picked} onChange={(e) => pick(e.target.value)}>
            <option value="" disabled>Select a district</option>
            {choices.map((item) => <option key={valueOf(item)} value={valueOf(item)}>{districtLabel(item)}</option>)}
          </select>
        </div>
      )}

      {choice && !signedIn && <p className="account-note" role="status">{districtLabel(choice)} will be saved after you sign in.</p>}
      {choice && signedIn && !saved && <button type="button" className="button" aria-disabled={saving} onClick={save}>{saving ? "Saving…" : "Save my district"}</button>}
      {saved && <p className="district-saved" role="status">Saved: {districtLabel(saved)}</p>}

      {saved && <FollowDelegation district={saved} onFollowed={onFollowed} />}

      {(saved || choice || selected?.state) && (() => {
        const target = saved ?? choice ?? selected;
        return <Link href={stateHref(target.state, "house", target.district)}>Explore {districtLabel(target)} →</Link>;
      })()}
      <a href="https://www.house.gov/representatives/find-your-representative" target="_blank" rel="noreferrer">Confirm your district on house.gov ↗</a>
    </section>
  );
}
