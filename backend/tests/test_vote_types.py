import pytest

from app.services.vote_types import congress_for_year, make_vote_id, normalize_policy_id, split_policy_id


@pytest.mark.parametrize("doc_type,number,congress,expected", [
    ("H.R.", "2", 118, "118-hr-2"),
    ("S.", "316", "118", "118-s-316"),
    ("S.J.Res.", "63", 117, "117-sjres-63"),
    ("H.Con.Res.", "14", 119, "119-hconres-14"),
    ("PN", "123", 119, "119-pn-123"),
    ("PN", "12-3", 119, "119-pn-12-3"),
    ("SJRES", "010", 119, "119-sjres-10"),
    ("Treaty Doc.", "118-1", 118, None),
    ("", "", 118, None),
    ("H.R.", "abc", 118, None),
])
def test_normalize_policy_id(doc_type, number, congress, expected):
    assert normalize_policy_id(doc_type, number, congress) == expected


def test_split_policy_id():
    assert split_policy_id("118-hr-2") == (118, "hr", "2")
    assert split_policy_id("119-pn-12-3") == (119, "pn", "12-3")
    with pytest.raises(ValueError):
        split_policy_id("118-xyz-2")


def test_vote_id_and_congress():
    assert make_vote_id(119, 1, 42) == "119-1-00042"
    assert congress_for_year(2025) == (119, 1)
    assert congress_for_year(2022) == (117, 2)
