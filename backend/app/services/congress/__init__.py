"""Congress.gov API v3 client: bills, nominations, CRS summaries, member photos (AGENTS.md §4.1)."""
import html
import re

import httpx

from app.models import LatestAction, Policy
from app.services.vote_types import split_policy_id

BASE = "https://api.congress.gov/v3"

# Congress.gov website URL slugs per bill type.
URL_SLUGS = {
    "s": "senate-bill", "hr": "house-bill",
    "sres": "senate-resolution", "hres": "house-resolution",
    "sjres": "senate-joint-resolution", "hjres": "house-joint-resolution",
    "sconres": "senate-concurrent-resolution", "hconres": "house-concurrent-resolution",
}
DISPLAY = {"s": "S.", "hr": "H.R.", "sres": "S.Res.", "hres": "H.Res.", "sjres": "S.J.Res.",
           "hjres": "H.J.Res.", "sconres": "S.Con.Res.", "hconres": "H.Con.Res.", "pn": "PN"}


class CongressApiError(Exception):
    pass


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def display_number(policy_type: str, number: str) -> str:
    """("hr", "2") -> "H.R. 2"."""
    return f"{DISPLAY.get(policy_type, policy_type.upper())} {number}"


def congress_gov_url(congress: int, policy_type: str, number: str) -> str:
    if policy_type == "pn":
        return f"https://www.congress.gov/nomination/{ordinal(congress)}-congress/{number.split('-')[0]}"
    return f"https://www.congress.gov/bill/{ordinal(congress)}-congress/{URL_SLUGS[policy_type]}/{number}"


class CongressClient:
    def __init__(self, client: httpx.AsyncClient, api_key: str):
        if not api_key:
            raise CongressApiError("CONGRESS_API_KEY is not set")
        self.client = client
        self.api_key = api_key

    async def _get(self, path: str, **params) -> dict:
        res = await self.client.get(f"{BASE}{path}", params={"api_key": self.api_key, "format": "json", **params})
        if res.status_code == 404:
            return {}
        if res.status_code >= 400:
            raise CongressApiError(f"Congress.gov {res.status_code} for {path}")
        return res.json()

    async def reachable(self) -> bool:
        """Congress.gov can accept connections and then never answer, so check once before bulk work."""
        try:
            res = await self.client.get(f"{BASE}/member/C000127", params={"api_key": self.api_key, "format": "json"},
                                        timeout=15.0)
        except httpx.HTTPError:
            return False
        return res.status_code < 500

    async def get_member_photo(self, bioguide_id: str) -> str | None:
        data = await self._get(f"/member/{bioguide_id}")
        return (data.get("member", {}).get("depiction") or {}).get("imageUrl")

    async def get_policy(self, policy_id: str, fallback_title: str | None = None) -> Policy:
        congress, ptype, number = split_policy_id(policy_id)
        if ptype == "pn":
            return await self._get_nomination(policy_id, congress, number, fallback_title)
        return await self._get_bill(policy_id, congress, ptype, number, fallback_title)

    async def _get_bill(self, policy_id, congress, ptype, number, fallback_title) -> Policy:
        bill = (await self._get(f"/bill/{congress}/{ptype}/{number}")).get("bill", {})
        summaries = (await self._get(f"/bill/{congress}/{ptype}/{number}/summaries")).get("summaries", [])
        latest_summary = max(summaries, key=lambda s: s.get("updateDate", ""), default=None)
        action = bill.get("latestAction") or {}
        return Policy(
            policy_id=policy_id, congress=congress, type=ptype, number=number,
            title=bill.get("title") or fallback_title or display_number(ptype, number),
            short_title=None,
            crs_summary=strip_html(latest_summary["text"]) if latest_summary else None,
            congress_gov_url=congress_gov_url(congress, ptype, number),
            latest_action=LatestAction(date=action["actionDate"], text=action.get("text", ""))
            if action.get("actionDate") else None,
        )

    async def _get_nomination(self, policy_id, congress, number, fallback_title) -> Policy:
        base_number = number.split("-")[0]
        nom = (await self._get(f"/nomination/{congress}/{base_number}")).get("nomination", {})
        action = nom.get("latestAction") or {}
        return Policy(
            policy_id=policy_id, congress=congress, type="pn", number=number,
            title=nom.get("description") or fallback_title or display_number("pn", number),
            short_title=None,
            crs_summary=None,
            congress_gov_url=congress_gov_url(congress, "pn", number),
            latest_action=LatestAction(date=action["actionDate"], text=action.get("text", ""))
            if action.get("actionDate") else None,
        )
