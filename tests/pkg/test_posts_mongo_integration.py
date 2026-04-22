"""CRUD integration tests against a real MongoDB instance (Docker via testcontainers)."""

from __future__ import annotations

import time
import uuid
from datetime import timezone

import pytest
from pymongo import MongoClient
from testcontainers.mongodb import MongoDbContainer

from pkg.posts import MongoPostRepository, PostRepository


@pytest.fixture
def mongo_repo(mongo_container: MongoDbContainer) -> MongoPostRepository:
    uri = mongo_container.get_connection_url()
    db_name = f"posts_{uuid.uuid4().hex}"
    client = MongoClient(uri)
    coll = client[db_name]["posts"]
    repo = MongoPostRepository(coll)
    yield repo
    client.drop_database(db_name)


@pytest.mark.integration
def test_mongo_repository_satisfies_protocol(mongo_repo: MongoPostRepository) -> None:
    assert isinstance(mongo_repo, PostRepository)


@pytest.mark.integration
def test_mongo_create_get_by_id_and_name(mongo_repo: MongoPostRepository) -> None:
    created = mongo_repo.create("  Alpha  ")
    assert created.name == "Alpha"

    by_id = mongo_repo.get_by_id(created.id)
    assert by_id is not None
    assert by_id.id == created.id
    assert by_id.name == "Alpha"
    assert by_id.created_at.tzinfo == timezone.utc

    by_name = mongo_repo.get_by_name("  Alpha ")
    assert by_name is not None
    assert by_name.id == created.id
    assert by_name.deleted_at is None


@pytest.mark.integration
def test_mongo_list_posts_sorted_by_created_at(mongo_repo: MongoPostRepository) -> None:
    first = mongo_repo.create("first")
    second = mongo_repo.create("second")
    listed = mongo_repo.list_posts()
    assert [p.id for p in listed] == [first.id, second.id]
    assert listed[0].created_at <= listed[1].created_at


@pytest.mark.integration
def test_mongo_update_name_and_timestamps(mongo_repo: MongoPostRepository) -> None:
    post = mongo_repo.create("old")
    created_at = post.created_at
    updated = mongo_repo.update(post.id, name="new")
    assert updated is not None
    assert updated.name == "new"
    # BSON Date has millisecond precision; round-trip may trim sub-ms.
    assert abs((updated.created_at - created_at).total_seconds()) < 0.001
    assert updated.updated_at >= updated.created_at
    assert mongo_repo.get_by_name("old") is None
    assert mongo_repo.get_by_name("new") is not None


@pytest.mark.integration
def test_mongo_update_same_name_refreshes_updated_at(
    mongo_repo: MongoPostRepository,
) -> None:
    post = mongo_repo.create("same")
    first_updated = post.updated_at
    time.sleep(0.02)
    updated = mongo_repo.update(post.id, name="same")
    assert updated is not None
    assert updated.updated_at >= first_updated


@pytest.mark.integration
def test_mongo_get_missing(mongo_repo: MongoPostRepository) -> None:
    assert mongo_repo.get_by_id(str(uuid.uuid4())) is None
    assert mongo_repo.get_by_name("nope") is None


@pytest.mark.integration
def test_mongo_get_by_name_blank(mongo_repo: MongoPostRepository) -> None:
    assert mongo_repo.get_by_name("   ") is None


@pytest.mark.integration
def test_mongo_create_rejects_blank_name(mongo_repo: MongoPostRepository) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        mongo_repo.create("  \t  ")


@pytest.mark.integration
def test_mongo_create_rejects_duplicate_name(mongo_repo: MongoPostRepository) -> None:
    mongo_repo.create("dup")
    with pytest.raises(ValueError, match="already exists"):
        mongo_repo.create("dup")


@pytest.mark.integration
def test_mongo_update_missing_returns_none(mongo_repo: MongoPostRepository) -> None:
    assert mongo_repo.update(str(uuid.uuid4()), name="x") is None


@pytest.mark.integration
def test_mongo_update_rejects_blank_name(mongo_repo: MongoPostRepository) -> None:
    post = mongo_repo.create("ok")
    with pytest.raises(ValueError, match="non-empty"):
        mongo_repo.update(post.id, name="  ")


@pytest.mark.integration
def test_mongo_update_rejects_duplicate_name(mongo_repo: MongoPostRepository) -> None:
    mongo_repo.create("a")
    b = mongo_repo.create("b")
    with pytest.raises(ValueError, match="already exists"):
        mongo_repo.update(b.id, name="a")


@pytest.mark.integration
def test_mongo_soft_delete_excludes_from_default_queries(
    mongo_repo: MongoPostRepository,
) -> None:
    post = mongo_repo.create("gone")
    assert mongo_repo.soft_delete(post.id) is not None
    assert mongo_repo.get_by_id(post.id) is None
    assert mongo_repo.list_posts() == []
    assert mongo_repo.get_by_id(post.id, include_deleted=True) is not None


@pytest.mark.integration
def test_mongo_reuse_name_after_soft_delete(mongo_repo: MongoPostRepository) -> None:
    first = mongo_repo.create("reuse")
    mongo_repo.soft_delete(first.id)
    second = mongo_repo.create("reuse")
    assert second.id != first.id
    found = mongo_repo.get_by_name("reuse")
    assert found is not None
    assert found.id == second.id


@pytest.mark.integration
def test_mongo_list_empty(mongo_container: MongoDbContainer) -> None:
    uri = mongo_container.get_connection_url()
    db_name = f"posts_empty_{uuid.uuid4().hex}"
    client = MongoClient(uri)
    try:
        coll = client[db_name]["posts"]
        repo = MongoPostRepository(coll)
        assert repo.list_posts() == []
    finally:
        client.drop_database(db_name)


@pytest.mark.integration
def test_mongo_create_with_image_urls_persists_listings(
    mongo_repo: MongoPostRepository,
) -> None:
    u = "https://storage.googleapis.com/bk/p/1.jpg"
    p = mongo_repo.create("list-host", image_urls=[u])
    assert p.image_urls == [u]
    assert len(p.listings) == 1
    assert p.listings[0].image_url == u
    again = mongo_repo.get_by_id(p.id)
    assert again is not None
    assert len(again.listings) == 1
