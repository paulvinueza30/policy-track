"""Single source for the rolling 4-year window (AGENTS.md §2, §9 rule 7)."""
from datetime import datetime, timezone

WINDOW_YEARS = 4


def window_end() -> datetime:
    return datetime.now(timezone.utc)


def window_start() -> datetime:
    end = window_end()
    try:
        return end.replace(year=end.year - WINDOW_YEARS)
    except ValueError:  # Feb 29 -> Feb 28
        return end.replace(year=end.year - WINDOW_YEARS, day=28)


def in_window(when: datetime) -> bool:
    return window_start() <= when <= window_end()
