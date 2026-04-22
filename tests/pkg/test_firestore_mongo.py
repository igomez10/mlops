from unittest.mock import MagicMock, patch

import pytest

from pkg.config import CloudSettings
from pkg.firestore_mongo import (
    FirestoreMongoCollection,
    FirestoreMongoDatabase,
)


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
