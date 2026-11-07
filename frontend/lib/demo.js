import states from "./states.json";

// Fictional records for the Stitch preview. Keep these separate from the API client.
export const demoSenators = [
  { id: "demo-jenkins", name: "Sen. Sarah Jenkins", portrait: "/votelens/jenkins.jpg", party: "Republican", seat: "Senior Senator" },
  { id: "demo-hayes", name: "Sen. Robert Hayes", portrait: "/votelens/hayes.jpg", party: "Republican", seat: "Junior Senator" },
];

export function getDemoDelegation(state) {
  if (state.code === "TX") return demoSenators;

  return ["Senior", "Junior"].map((role) => ({
    id: `demo-${state.code.toLowerCase()}-${role.toLowerCase()}`,
    name: `${state.name} ${role} Senator`,
    seat: `${role} Senator`,
    initials: state.code,
  }));
}

export function getDemoProfile(id) {
  const texasSenator = demoSenators.find((senator) => senator.id === id);
  if (texasSenator) return { senator: texasSenator, state: states.find(({ code }) => code === "TX") };

  const match = /^demo-([a-z]{2})-(senior|junior)$/.exec(id);
  if (!match) return null;
  const state = states.find(({ code }) => code.toLowerCase() === match[1]);
  if (!state) return null;
  const senator = getDemoDelegation(state).find((item) => item.id === id);
  return senator ? { senator, state } : null;
}

export const demoPolicies = [
  {
    id: "demo-insulin",
    topic: "Healthcare",
    title: "Bipartisan Commercial Insulin Price Ceiling & PBM Transparency Act",
    date: "2026-10-22",
    result: "Passed",
    tally: { Yea: 63, Nay: 35, Present: 0, "Not Voting": 2 },
    positions: ["Yea", "Nay"],
    headline: "Senate debates how widely to apply a proposed insulin price ceiling",
    summary: "In this sample, the measure caps out-of-pocket insulin costs for some people with commercial insurance. It also asks pharmacy benefit managers to disclose more about how drug prices are set.",
  },
  {
    id: "demo-grid",
    topic: "Energy",
    title: "National Energy Grid Hardening and Domestic Lithium Battery Supply Act",
    date: "2026-09-17",
    result: "Passed",
    tally: { Yea: 68, Nay: 30, Present: 0, "Not Voting": 2 },
    positions: ["Yea", "Yea"],
    headline: "Federal energy regulators outline sample grants for grid resilience",
    summary: "The example measure funds upgrades to parts of the electrical grid and supports domestic battery supply. The sample grants are aimed at reducing disruptions during severe weather.",
  },
  {
    id: "demo-drought",
    topic: "Agriculture",
    title: "Western Drought Emergency Relief & Federal Livestock Grazing Restructuring Act",
    date: "2026-08-05",
    result: "Rejected",
    tally: { Yea: 46, Nay: 53, Present: 0, "Not Voting": 1 },
    positions: ["Nay", "Yea"],
    headline: "Drought relief and grazing rules emerge as sticking points in Senate debate",
    summary: "This sample proposal offers temporary drought assistance and revises federal grazing rules. The example vote shows the proposal falling short of the votes needed to pass.",
  },
];

export function formatDemoDate(date) {
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(date));
}
