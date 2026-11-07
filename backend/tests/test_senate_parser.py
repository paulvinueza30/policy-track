import pytest

from app.services.senate import SenateBlockedError, normalize_cast, parse_vote, parse_vote_menu


def test_parse_vote(fixture_bytes):
    v = parse_vote(fixture_bytes("senate_vote_118_1_00042.xml"))
    assert v.vote_id == "118-1-00042"
    assert v.policy_id == "118-s-316"
    assert v.date.year == 2023 and v.date.month == 3 and v.date.day == 29 and v.date.hour == 12
    assert v.result == "Bill Passed (66-30)"
    assert [(p.member_key, p.position) for p in v.positions] == [
        ("S275", "Yea"), ("S221", "Not Voting"), ("S174", "Nay")]
    assert v.tally() == {"yea": 1, "nay": 1, "present": 0, "notVoting": 1}


def test_parse_vote_menu(fixture_bytes):
    menu = parse_vote_menu(fixture_bytes("senate_vote_menu_118_1.xml"))
    assert [n for n, _ in menu] == [1, 2]
    assert menu[1][1].month == 1 and menu[1][1].day == 26


def test_blocked_page_raises():
    html = b"<!DOCTYPE HTML><html><head><title>Senate.gov - Unauthorized</title></head></html>"
    with pytest.raises(SenateBlockedError):
        parse_vote(html)


@pytest.mark.parametrize("cast,expected", [
    ("Yea", "Yea"), ("Nay", "Nay"), ("Not Voting", "Not Voting"),
    ("Present, Giving Live Pair", "Present"), ("Guilty", "Yea"), ("Not Guilty", "Nay"),
])
def test_normalize_cast(cast, expected):
    assert normalize_cast(cast) == expected
