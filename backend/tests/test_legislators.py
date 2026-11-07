import json
from datetime import datetime, timezone

from app.services.legislators import build_index

START = datetime(2022, 11, 7, tzinfo=timezone.utc)
END = datetime(2026, 11, 7, tzinfo=timezone.utc)


def test_build_index(fixture_text):
    people = json.loads(fixture_text("legislators_sample.json"))
    idx = build_index(people, START, END, now=END)
    assert set(idx.senators) == {"C000127", "B000575", "F000062", "M000355"}  # 1790s senator excluded
    assert idx.resolve("S221") == "F000062"
    assert idx.resolve("M000355") == "M000355"
    assert idx.resolve("S999") is None
    assert idx.senators["C000127"].in_office_to is None
    assert idx.senators["F000062"].in_office_to.year == 2023
    assert idx.senators["C000127"].state == "WA"
