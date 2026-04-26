from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

if TYPE_CHECKING:
    from pkg.config import CloudSettings

_DEFAULT_FIND_LIMIT = 100
_MAX_FIND_LIMIT = 500


@dataclass(frozen=True)
class InsertOneResult:
    inserted_id: str


@dataclass(frozen=True)
class UpdateResult:
    matched_count: int
    modified_count: int


@dataclass(frozen=True)
class DeleteResult:
    deleted_count: int


def _normalize_id(value: Any) -> str:
    return str(value)


def _with_id(doc_id: str, data: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(data or {})
    return {"_id": doc_id, **payload}


class FirestoreMongoCollection:
    """MongoDB-style API subset backed by a Firestore collection reference."""

    def __init__(self, collection: firestore.CollectionReference) -> None:
        self._coll = collection

    def insert_one(self, document: dict[str, Any]) -> InsertOneResult:
        doc = dict(document)
        doc_id = doc.pop("_id", None)
        if doc_id is not None:
            doc_id_s = _normalize_id(doc_id)
            self._coll.document(doc_id_s).set(doc)
            return InsertOneResult(inserted_id=doc_id_s)
        _, ref = self._coll.add(doc)
        return InsertOneResult(inserted_id=ref.id)

    def find_one(self, filter: dict[str, Any]) -> dict[str, Any] | None:  # noqa: A002
        if "_id" in filter:
            if len(filter) != 1:
                raise ValueError("When filtering by _id, no other fields may be present")
            snap = self._coll.document(_normalize_id(filter["_id"])).get()
            if not snap.exists:  # type: ignore[union-attr]
                return None
            return _with_id(snap.id, snap.to_dict())  # type: ignore[union-attr]

        query: firestore.Query = self._coll  # type: ignore[assignment]
        for key, value in filter.items():
            query = query.where(filter=FieldFilter(key, "==", value))
        for snap in query.limit(1).stream():
            return _with_id(snap.id, snap.to_dict())
        return None

    def find(
        self,
        filter: dict[str, Any] | None = None,  # noqa: A002
        *,
        limit: int = _DEFAULT_FIND_LIMIT,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if limit > _MAX_FIND_LIMIT:
            raise ValueError(f"limit cannot exceed {_MAX_FIND_LIMIT}")

        filter = filter or {}
        if "_id" in filter:
            if len(filter) != 1:
                raise ValueError("When filtering by _id, no other fields may be present")
            one = self.find_one(filter)
            return [one] if one else []

        query: firestore.Query = self._coll  # type: ignore[assignment]
        for key, value in filter.items():
            query = query.where(filter=FieldFilter(key, "==", value))
        return [_with_id(snap.id, snap.to_dict()) for snap in query.limit(limit).stream()]

    def update_one(
        self,
        filter: dict[str, Any],  # noqa: A002
        update: dict[str, Any],
    ) -> UpdateResult:
        if "$set" in update:
            payload = update["$set"]
            if not isinstance(payload, dict):
                raise TypeError("$set value must be a dict")
        else:
            if any(isinstance(k, str) and k.startswith("$") for k in update):
                raise ValueError("Only $set updates are supported")
            payload = update

        existing = self.find_one(filter)
        if existing is None:
            return UpdateResult(matched_count=0, modified_count=0)

        doc_id = _normalize_id(existing["_id"])
        self._coll.document(doc_id).update(payload)
        return UpdateResult(matched_count=1, modified_count=1)

    def delete_one(self, filter: dict[str, Any]) -> DeleteResult:  # noqa: A002
        existing = self.find_one(filter)
        if existing is None:
            return DeleteResult(deleted_count=0)
        self._coll.document(_normalize_id(existing["_id"])).delete()
        return DeleteResult(deleted_count=1)


class FirestoreMongoDatabase:
    """Firestore client exposed as a MongoDB-flavored database object."""

    def __init__(self, client: firestore.Client) -> None:
        self._client = client

    @classmethod
    def from_settings(cls, settings: CloudSettings) -> FirestoreMongoDatabase:
        kwargs: dict[str, Any] = {"database": settings.firestore_database_id}
        if settings.gcp_project_id:
            kwargs["project"] = settings.gcp_project_id
        return cls(firestore.Client(**kwargs))

    def collection(self, name: str) -> FirestoreMongoCollection:
        return FirestoreMongoCollection(self._client.collection(name))
