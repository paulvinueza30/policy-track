"use client";

import { useRouter } from "next/navigation";

export default function StatePicker({ options, stateCode, chamber = "senate" }) {
  const router = useRouter();

  function openState(event) {
    event.preventDefault();
    const state = new FormData(event.currentTarget).get("state");
    if (options.some(({ code }) => code === state)) router.push("/state/" + state + "?chamber=" + chamber);
  }

  return (
    <form className="state-picker" onSubmit={openState}>
      <label htmlFor="state-picker" className="eyebrow">Find your state</label>
      <div className="picker-controls">
        <select id="state-picker" name="state" defaultValue={stateCode} required>
          <option value="" disabled>Select a state</option>
          {options.map(({ code, name }) => <option value={code} key={code}>{name}</option>)}
        </select>
        <button className="button" type="submit">Explore</button>
      </div>
    </form>
  );
}
