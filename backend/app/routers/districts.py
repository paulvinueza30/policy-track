"""ZIP crosswalk candidates, never an exact address-to-district claim."""
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException, Path
from app.config import settings
from app.deps import get_http

router = APIRouter(tags=["districts"])
FIPS = dict(item.split(":") for item in "01:AL 02:AK 04:AZ 05:AR 06:CA 08:CO 09:CT 10:DE 12:FL 13:GA 15:HI 16:ID 17:IL 18:IN 19:IA 20:KS 21:KY 22:LA 23:ME 24:MD 25:MA 26:MI 27:MN 28:MS 29:MO 30:MT 31:NE 32:NV 33:NH 34:NJ 35:NM 36:NY 37:NC 38:ND 39:OH 40:OK 41:OR 42:PA 44:RI 45:SC 46:SD 47:TN 48:TX 49:UT 50:VT 51:VA 53:WA 54:WV 55:WI 56:WY".split())
_cache: dict[str, tuple[float, dict]] = {}


@router.get("/districts/zip/{zipcode}")
async def lookup(zipcode: str = Path(pattern=r"^\d{5}$"), client: httpx.AsyncClient = Depends(get_http)) -> dict:
    if zipcode in _cache and _cache[zipcode][0] > time.time():
        return _cache[zipcode][1]
    if not settings.hud_api_key:
        raise HTTPException(503, "ZIP lookup is not configured. Choose your state and district manually.")
    try:
        response = await client.get("https://www.huduser.gov/hudapi/public/usps",
                                    params={"type": 5, "query": zipcode, "year": 2025, "quarter": 4},
                                    headers={"Authorization": f"Bearer {settings.hud_api_key}"})
        if response.status_code == 404:
            raise HTTPException(404, "No district matches were found for this ZIP code")
        response.raise_for_status()
        data = response.json()["data"]
        blocks = data if isinstance(data, list) else [data]
        candidates = {}
        for block in blocks:
            for item in block.get("results", []):
                geoid = str(item.get("geoid", item.get("cd", ""))).zfill(4)
                if len(geoid) == 4 and geoid[:2] in FIPS and geoid[2:].isdigit():
                    candidates[geoid] = {"state": FIPS[geoid[:2]], "district": int(geoid[2:])}
        result = {"zip": zipcode, "districts": list(candidates.values()), "congress": 119,
                  "source": "HUD USPS crosswalk, 2025 Q4", "requiresConfirmation": True}
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        raise HTTPException(503, "ZIP lookup is unavailable. Choose your district manually.") from exc
    if len(_cache) >= 1000:
        _cache.clear()
    _cache[zipcode] = (time.time() + 86400, result)
    return result
