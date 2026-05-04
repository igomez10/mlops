from __future__ import annotations

from datetime import datetime, timezone

from pkg.ebay_tokens import EbayUserToken, MongoEbayTokenRepository


class _FakeCollection:
    def __init__(self) -> None:
        self.existing = {"_id": "user-1", "user_id": "user-1"}
        self.updated_filter = None
        self.updated_doc = None

    def create_index(self, *args, **kwargs) -> None:
        return None

    def find_one(self, query):
        if query == {"user_id": "user-1"}:
            return self.existing
        return None

    def insert_one(self, doc) -> None:
        raise AssertionError("insert_one should not be called for an existing token")

    def update_one(self, query, update) -> None:
        self.updated_filter = query
        self.updated_doc = update


def test_mongo_upsert_does_not_try_to_set_id():
    coll = _FakeCollection()
    repo = MongoEbayTokenRepository(coll)
    token = EbayUserToken(
        user_id="user-1",
        access_token="access",
        refresh_token="refresh",
        token_type="Bearer",
        scopes=["scope-1"],
        expires_at=datetime.now(timezone.utc),
    )

    repo.upsert(token)

    assert coll.updated_filter == {"user_id": "user-1"}
    assert coll.updated_doc is not None
    assert "$set" in coll.updated_doc
    assert "_id" not in coll.updated_doc["$set"]
