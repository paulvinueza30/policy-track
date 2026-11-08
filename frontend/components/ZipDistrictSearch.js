"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, lookupZip } from "@/lib/api";
import { districtLabel, findState, stateHref } from "@/lib/display";

const NO_MATCHES = "No matching districts were found for this ZIP code. Choose your district from the list above.";

function failureMessage(error) {
  if (!(error instanceof ApiError) || error.status === 0) return "ZIP search couldn’t be reached. Choose your district from the list above.";
  if (error.status === 404) return NO_MATCHES;
  if (error.status === 422) return "Enter a valid 5-digit ZIP code.";
  return error.message;
}

/** Public ZIP search for the House view. The ZIP is only sent for the lookup and is never saved. */
export default function ZipDistrictSearch() {
  const router = useRouter();
  const [zip, setZip] = useState("");
  const [choices, setChoices] = useState([]);
  const [picked, setPicked] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const latest = useRef(0);

  function clearResults() {
    latest.current += 1;
    setChoices([]);
    setPicked("");
    setError("");
    setBusy(false);
  }

  async function search(event) {
    event.preventDefault();
    clearResults();
    if (!/^\d{5}$/.test(zip)) {
      setError("Enter a 5-digit ZIP code.");
      return;
    }
    const id = latest.current;
    setBusy(true);
    try {
      const result = await lookupZip(zip);
      if (id !== latest.current) return;
      const found = (result.districts ?? []).filter((choice) => findState(choice.state) && Number.isInteger(choice.district));
      setChoices(found);
      if (!found.length) setError(NO_MATCHES);
    } catch (e) {
      if (id === latest.current) setError(failureMessage(e));
    } finally {
      if (id === latest.current) setBusy(false);
    }
  }

  function confirm(event) {
    event.preventDefault();
    const choice = choices.find((item) => item.state + ":" + item.district === picked);
    if (!choice) return;
    clearResults();
    setZip("");
    router.push(stateHref(choice.state, "house", choice.district), { scroll: false });
  }

  return (
    <div className="zip-search">
      <form className="lookup-form" onSubmit={search} noValidate>
        <label htmlFor="district-zip">Find your district by ZIP</label>
        <div className="picker-controls">
          <input id="district-zip" inputMode="numeric" autoComplete="postal-code" maxLength={5} value={zip} aria-describedby="district-zip-note"
            onChange={(event) => { setZip(event.target.value.replace(/\D/g, "").slice(0, 5)); clearResults(); }} />
          <button className="button" type="submit" disabled={busy}>Look up</button>
        </div>
      </form>
      <p className="map-note" id="district-zip-note">A ZIP code can cross district lines. Confirm your district below.</p>
      {busy && <p role="status">Finding districts…</p>}
      {error && <p role="alert">{error}</p>}
      {choices.length > 0 && (
        <form className="zip-choices" onSubmit={confirm}>
          <fieldset>
            <legend>Confirm your district</legend>
            {choices.map((choice) => {
              const value = choice.state + ":" + choice.district;
              return (
                <label key={value}>
                  <input type="radio" name="zip-district" value={value} checked={picked === value} onChange={() => setPicked(value)} />
                  {districtLabel(choice)}
                </label>
              );
            })}
          </fieldset>
          <button className="button" type="submit" disabled={!picked}>Go to this district</button>
        </form>
      )}
    </div>
  );
}
