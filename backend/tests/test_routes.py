from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.deps import get_repo
from app.main import app

NOW = datetime.now(timezone.utc)


def vote_doc(n: int, days_ago: int, position: str | None = None, policy_id: str | None = "119-hr-1") -> dict:
    d = {"voteId": f"119-1-{n:05d}", "congress": 119, "session": 1, "voteNumber": n,
         "date": NOW - timedelta(days=days_ago), "question": "On Passage", "result": "Passed",
         "policyId": policy_id, "tally": {"yea": 51, "nay": 49, "present": 0, "notVoting": 0}}
    if position:
        d["position"] = position
    return d


class FakeRepo:
    senators = {
        "C000127": {"bioguideId": "C000127", "lisId": "S275", "name": "Maria Cantwell", "party": "Democrat",
                    "state": "WA", "inOfficeFrom": NOW - timedelta(days=9000), "inOfficeTo": None},
        "M000355": {"bioguideId": "M000355", "lisId": "S174", "name": "Mitch McConnell", "party": "Republican",
                    "state": "KY", "inOfficeFrom": NOW - timedelta(days=9000), "inOfficeTo": None},
    }

    def __init__(self):
        self.calls = []
        self.articles = []
        self.policy = {"policyId": "119-hr-1", "congress": 119, "type": "hr", "number": "1",
                       "title": "One Big Beautiful Bill Act", "crsSummary": "Summary"}

    async def senators_by_state(self, state):
        return [s for s in self.senators.values() if s["state"] == state]

    async def get_senator(self, b):
        return self.senators.get(b)

    async def senator_votes(self, b, start, end, position, page, page_size):
        self.calls.append((start, end, position, page, page_size))
        return [vote_doc(2, 1, "Yea"), vote_doc(1, 5, "Nay")], 2

    async def get_vote(self, vote_id):
        if vote_id != "119-1-00002":
            return None
        return {**vote_doc(2, 1), "members": [
            {"voteId": vote_id, "bioguideId": "M000355", "position": "Nay", "name": "Mitch McConnell",
             "party": "Republican", "state": "KY"},
            {"voteId": vote_id, "bioguideId": "C000127", "position": "Yea", "name": "Maria Cantwell",
             "party": "Democrat", "state": "WA"}]}

    async def get_policy(self, pid):
        return self.policy if pid == "119-hr-1" else None

    async def policy_votes(self, pid):
        return [vote_doc(2, 1), vote_doc(1, 5)]

    async def get_articles(self, pid):
        return self.articles

    async def replace_articles(self, pid, articles, fetched_at):
        self.articles = [a.model_dump(by_alias=True) for a in articles]
        self.policy["articlesFetchedAt"] = fetched_at


@pytest.fixture
def repo():
    r = FakeRepo()
    app.dependency_overrides[get_repo] = lambda: r
    yield r
    app.dependency_overrides.clear()


client = TestClient(app)


def test_state_senators(repo):
    r = client.get("/api/states/wa/senators")
    assert r.status_code == 200
    assert [s["bioguideId"] for s in r.json()] == ["C000127"]
    assert r.json()[0]["inOfficeTo"] is None


def test_bad_state(repo):
    r = client.get("/api/states/ZZ/senators")
    assert r.status_code == 400 and r.json()["error"]["code"] == "http_400"


def test_senator_and_404(repo):
    assert client.get("/api/senators/c000127").json()["name"] == "Maria Cantwell"
    r = client.get("/api/senators/X000000")
    assert r.status_code == 404 and "not found" in r.json()["error"]["message"]


def test_senator_votes(repo):
    r = client.get("/api/senators/C000127/votes", params={"from": "2025-01-01", "position": "Yea", "page": 2})
    body = r.json()
    assert r.status_code == 200 and body["total"] == 2 and body["page"] == 2
    assert body["items"][0]["position"] == "Yea" and body["items"][0]["voteId"] == "119-1-00002"
    start, end, position, page, size = repo.calls[0]
    assert start.year == 2025 and position == "Yea" and page == 2 and size == 25


def test_senator_votes_bad_position(repo):
    r = client.get("/api/senators/C000127/votes", params={"position": "Maybe"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_vote(repo):
    body = client.get("/api/votes/119-1-00002").json()
    assert [m["state"] for m in body["senatorVotes"]] == ["KY", "WA"]
    assert client.get("/api/votes/nope").status_code == 400
    assert client.get("/api/votes/119-1-00009").status_code == 404


def test_policy(repo):
    body = client.get("/api/policies/119-HR-1").json()
    assert body["title"] == "One Big Beautiful Bill Act"
    assert len(body["votes"]) == 2
    assert client.get("/api/policies/bad").status_code == 400


def test_articles_without_key_returns_503(repo, monkeypatch):
    monkeypatch.setattr("app.routers.policies.settings.news_api_key", "")
    r = client.get("/api/policies/119-hr-1/articles")
    assert r.status_code == 503 and r.json()["error"]["message"].startswith("News is unavailable")


def test_articles_served_from_fresh_cache(repo):
    repo.policy["articlesFetchedAt"] = NOW
    repo.articles = [{"policyId": "119-hr-1", "title": "T", "source": "S", "url": "https://x.test",
                      "publishedAt": NOW, "description": None}]
    assert client.get("/api/policies/119-hr-1/articles").json()[0]["title"] == "T"


def test_unknown_route_uses_error_shape(repo):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "http_404"
