"""The 50 state codes (Senate only, so no DC or territories)."""
STATE_CODES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO "
    "MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)


def normalize_state(code: str) -> str | None:
    code = (code or "").strip().upper()
    return code if code in STATE_CODES else None
