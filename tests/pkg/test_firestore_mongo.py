from unittest.mock import MagicMock, patch

import pytest

from pkg.config import CloudSettings
from pkg.firestore_mongo import (
    FirestoreMongoCollection,
    FirestoreMongoDatabase,
)
from pkg.posts import MongoPostRepository


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict | None):
        self.id = doc_id
        self._data = None if data is None else dict(data)
        self.exists = data is not None

    def to_dict(self):
        return None if self._data is None else dict(self._data)


class _FakeDocumentRef:
    def __init__(self, collection: "_FakeCollectionRef", doc_id: str):
        self._collection = collection
        self.id = doc_id

    def set(self, data: dict) -> None:
        self._collection._docs[self.id] = dict(data)

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self.id, self._collection._docs.get(self.id))

    def update(self, data: dict) -> None:
        current = dict(self._collection._docs[self.id])
        current.update(data)
        self._collection._docs[self.id] = current

    def delete(self) -> None:
        self._collection._docs.pop(self.id, None)


class _FakeQuery:
    def __init__(
        self,
        collection: "_FakeCollectionRef",
        filters: list[tuple[str, object]] | None = None,
        limit_value: int | None = None,
    ):
        self._collection = collection
        self._filters = filters or []
        self._limit = limit_value

    def where(self, *, filter) -> "_FakeQuery":
        field_path = getattr(filter, "field_path", None) or getattr(filter, "_field_path", None)
        value = getattr(filter, "value", None)
        return _FakeQuery(
            self._collection,
            [*self._filters, (field_path, value)],
            self._limit,
        )

    def limit(self, value: int) -> "_FakeQuery":
        return _FakeQuery(self._collection, list(self._filters), value)

    def stream(self):
        rows: list[_FakeSnapshot] = []
        for doc_id, data in self._collection._docs.items():
            if all(data.get(field) == value for field, value in self._filters):
                rows.append(_FakeSnapshot(doc_id, data))
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows


class _FakeCollectionRef(_FakeQuery):
    def __init__(self):
        self._docs: dict[str, dict] = {}
        self._counter = 0
        super().__init__(self)

    def document(self, doc_id: str) -> _FakeDocumentRef:
        return _FakeDocumentRef(self, doc_id)

    def add(self, data: dict):
        self._counter += 1
        doc_id = f"auto-{self._counter}"
        ref = self.document(doc_id)
        ref.set(data)
        return (None, ref)


def test_insert_one_auto_id():
    coll_ref = MagicMock()
    doc_ref = MagicMock()
    doc_ref.id = "auto-1"
    coll_ref.add.return_value = (None, doc_ref)

    coll = FirestoreMongoCollection(coll_ref)
    res = coll.insert_one({"a": 1})
    assert res.inserted_id == "auto-1"
    coll_ref.add.assert_called_once_with({"a": 1})


def test_insert_one_with_explicit_id():
    coll_ref = MagicMock()
    doc_ref = MagicMock()
    coll_ref.document.return_value = doc_ref

    coll = FirestoreMongoCollection(coll_ref)
    res = coll.insert_one({"_id": "user-1", "a": 2})
    assert res.inserted_id == "user-1"
    coll_ref.document.assert_called_once_with("user-1")
    doc_ref.set.assert_called_once_with({"a": 2})


def test_find_one_by_id():
    coll_ref = MagicMock()
    snap = MagicMock()
    snap.exists = True
    snap.id = "user-1"
    snap.to_dict.return_value = {"a": 1}
    doc_ref = MagicMock()
    doc_ref.get.return_value = snap
    coll_ref.document.return_value = doc_ref

    coll = FirestoreMongoCollection(coll_ref)
    found = coll.find_one({"_id": "user-1"})
    assert found == {"_id": "user-1", "a": 1}


def test_find_one_by_id_missing():
    coll_ref = MagicMock()
    snap = MagicMock()
    snap.exists = False
    doc_ref = MagicMock()
    doc_ref.get.return_value = snap
    coll_ref.document.return_value = doc_ref

    coll = FirestoreMongoCollection(coll_ref)
    assert coll.find_one({"_id": "missing"}) is None


def test_find_one_rejects_id_with_extra_fields():
    coll_ref = MagicMock()
    coll = FirestoreMongoCollection(coll_ref)
    with pytest.raises(ValueError, match="_id"):
        coll.find_one({"_id": "x", "a": 1})


def test_find_applies_limit_and_returns_list():
    coll_ref = MagicMock()
    query = MagicMock()
    coll_ref.where.return_value = query
    query.where.return_value = query

    snap = MagicMock()
    snap.id = "d1"
    snap.to_dict.return_value = {"k": "v"}
    query.limit.return_value.stream.return_value = [snap]

    coll = FirestoreMongoCollection(coll_ref)
    rows = coll.find({"k": "v"}, limit=10)
    assert rows == [{"_id": "d1", "k": "v"}]
    query.limit.assert_called_once_with(10)


def test_find_by_id_only():
    coll_ref = MagicMock()
    snap = MagicMock()
    snap.exists = True
    snap.id = "only"
    snap.to_dict.return_value = {"x": 1}
    doc_ref = MagicMock()
    doc_ref.get.return_value = snap
    coll_ref.document.return_value = doc_ref

    coll = FirestoreMongoCollection(coll_ref)
    assert coll.find({"_id": "only"}, limit=5) == [{"_id": "only", "x": 1}]


def test_find_rejects_excessive_limit():
    coll_ref = MagicMock()
    coll = FirestoreMongoCollection(coll_ref)
    with pytest.raises(ValueError, match="limit"):
        coll.find(limit=9999)


def test_update_one_sets_fields():
    coll_ref = MagicMock()
    snap = MagicMock()
    snap.exists = True
    snap.id = "u1"
    snap.to_dict.return_value = {"a": 1}
    doc_ref = MagicMock()
    doc_ref.get.return_value = snap
    coll_ref.document.return_value = doc_ref

    coll = FirestoreMongoCollection(coll_ref)
    res = coll.update_one({"_id": "u1"}, {"$set": {"a": 2}})
    assert res.matched_count == 1
    assert res.modified_count == 1
    coll_ref.document.assert_called_with("u1")
    doc_ref.update.assert_called_once_with({"a": 2})


def test_update_one_no_match():
    coll_ref = MagicMock()
    snap = MagicMock()
    snap.exists = False
    doc_ref = MagicMock()
    doc_ref.get.return_value = snap
    coll_ref.document.return_value = doc_ref

    coll = FirestoreMongoCollection(coll_ref)
    res = coll.update_one({"_id": "nope"}, {"$set": {"a": 1}})
    assert res.matched_count == 0
    assert res.modified_count == 0


def test_delete_one_removes_document():
    coll_ref = MagicMock()
    snap = MagicMock()
    snap.exists = True
    snap.id = "d1"
    snap.to_dict.return_value = {}
    doc_ref = MagicMock()
    doc_ref.get.return_value = snap
    coll_ref.document.return_value = doc_ref

    coll = FirestoreMongoCollection(coll_ref)
    res = coll.delete_one({"_id": "d1"})
    assert res.deleted_count == 1
    doc_ref.delete.assert_called_once()


def test_firestore_mongo_database_collection():
    client = MagicMock()
    coll_ref = MagicMock()
    client.collection.return_value = coll_ref

    db = FirestoreMongoDatabase(client)
    wrapped = db.collection("posts")
    assert isinstance(wrapped, FirestoreMongoCollection)
    client.collection.assert_called_once_with("posts")


def test_firestore_mongo_database_from_settings(monkeypatch):
    monkeypatch.setenv("FIRESTORE_DATABASE_ID", "(default)")
    monkeypatch.setenv("GCP_PROJECT", "p1")

    with patch("pkg.firestore_mongo.firestore.Client") as mock_client_cls:
        FirestoreMongoDatabase.from_settings(CloudSettings.from_env())
        mock_client_cls.assert_called_once_with(database="(default)", project="p1")


def test_mongo_repository_works_with_firestore_collection_wrapper():
    coll = FirestoreMongoCollection(_FakeCollectionRef())
    repo = MongoPostRepository(coll)

    created = repo.create("firestore post", description="stored in firestore")
    assert created.name == "firestore post"
    assert created.description == "stored in firestore"

    fetched = repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id

    assert repo.get_by_name("firestore post") is not None
    listed = repo.list_posts()
    assert [p.id for p in listed] == [created.id]

    updated = repo.update(created.id, name="renamed", description="updated")
    assert updated is not None
    assert updated.name == "renamed"
    assert updated.description == "updated"

    deleted = repo.soft_delete(created.id)
    assert deleted is not None
    assert deleted.deleted_at is not None
    assert repo.get_by_id(created.id) is None
    assert repo.get_by_id(created.id, include_deleted=True) is not None
