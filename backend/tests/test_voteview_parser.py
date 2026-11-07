from app.services.voteview import parse_congress, split_bill_number


def test_split_bill_number():
    assert split_bill_number("SJRES10") == ("SJRES", "10")
    assert split_bill_number("PN1129") == ("PN", "1129")
    assert split_bill_number("") == (None, None)


def test_parse_congress(fixture_text):
    votes = parse_congress(fixture_text("voteview_S119_rollcalls.csv"),
                           fixture_text("voteview_S119_votes.csv"),
                           fixture_text("voteview_S119_members.csv"))
    assert [v.vote_id for v in votes] == ["119-1-00001", "119-1-00002"]
    first = votes[0]
    assert first.policy_id == "119-s-5"
    assert first.date.strftime("%Y-%m-%d") == "2025-01-09"
    assert first.source == "voteview"
    tally = first.tally()
    # Official count for this vote was 84-9.
    assert tally["yea"] == 84 and tally["nay"] == 9
    assert all(p.member_key[0].isalpha() for p in first.positions)  # bioguide ids
