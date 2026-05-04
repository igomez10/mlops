from datetime import datetime, timezone

import pytest

from pkg.posts import InMemoryPostRepository, Listing


def test_create_sets_id_and_timestamps():
    repo = InMemoryPostRepository()
    before = datetime.now(timezone.utc)
    post = repo.create("  Hello  ")
    after = datetime.now(timezone.utc)

    assert post.id
    assert post.name == "Hello"
    assert before <= post.created_at <= after
    assert post.created_at == post.updated_at
    assert post.deleted_at is None
    assert post.listings == []
    assert post.image_urls == []


def test_create_with_image_urls_produces_synthetic_listings():
    repo = InMemoryPostRepository()
    urls = [
        "posts/p1/aaaa.png",
        "posts/p1/bbbb.png",
    ]
    post = repo.create("Items", image_urls=urls)
    assert post.image_urls == urls
    assert len(post.listings) == 2
    for i, L in enumerate(post.listings):
        assert L.image_url == urls[i]
        assert L.status == "draft"
        assert "Items" in L.description
        assert "local.invalid" in L.marketplace_url


def test_get_by_id():
    repo = InMemoryPostRepository()
    created = repo.create("a")
    found = repo.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id
    assert found.name == "a"


def test_get_by_id_missing():
    assert InMemoryPostRepository().get_by_id("nope") is None


def test_get_by_name():
    repo = InMemoryPostRepository()
    repo.create("alpha")
    found = repo.get_by_name("  alpha ")
    assert found is not None
    assert found.name == "alpha"


def test_get_by_name_missing_and_blank():
    repo = InMemoryPostRepository()
    assert repo.get_by_name("x") is None
    assert repo.get_by_name("   ") is None


def test_list_posts_sorted_by_created_at():
    repo = InMemoryPostRepository()
    first = repo.create("first")
    second = repo.create("second")
    listed = repo.list_posts()
    assert [p.id for p in listed] == [first.id, second.id]


def test_list_posts_empty():
    assert InMemoryPostRepository().list_posts() == []


def test_create_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        InMemoryPostRepository().create("  \t  ")


def test_create_rejects_duplicate_name():
    repo = InMemoryPostRepository()
    repo.create("dup")
    with pytest.raises(ValueError, match="already exists"):
        repo.create("dup")


def test_create_rejects_duplicate_after_normalize():
    repo = InMemoryPostRepository()
    repo.create("Hello")
    with pytest.raises(ValueError, match="already exists"):
        repo.create("  Hello  ")


def test_update_changes_name_and_updated_at():
    repo = InMemoryPostRepository()
    post = repo.create("old")
    created_at = post.created_at
    updated = repo.update(post.id, name="new")
    assert updated is not None
    assert updated.name == "new"
    assert updated.created_at == created_at
    assert updated.updated_at >= updated.created_at
    assert repo.get_by_name("old") is None
    assert repo.get_by_name("new") is not None


def test_update_missing_returns_none():
    assert InMemoryPostRepository().update("missing-id", name="x") is None


def test_update_rejects_blank_name():
    repo = InMemoryPostRepository()
    post = repo.create("ok")
    with pytest.raises(ValueError, match="non-empty"):
        repo.update(post.id, name="  ")


def test_update_rejects_duplicate_name():
    repo = InMemoryPostRepository()
    a = repo.create("a")
    repo.create("b")
    with pytest.raises(ValueError, match="already exists"):
        repo.update(a.id, name="b")


def test_update_same_name_refreshes_updated_at():
    repo = InMemoryPostRepository()
    post = repo.create("same")
    first_updated = post.updated_at
    updated = repo.update(post.id, name="same")
    assert updated is not None
    assert updated.name == "same"
    assert updated.updated_at >= first_updated


def test_post_repository_protocol_runtime_check():
    repo = InMemoryPostRepository()
    from pkg.posts import PostRepository

    assert isinstance(repo, PostRepository)


def test_soft_delete_hides_from_get_and_list():
    repo = InMemoryPostRepository()
    post = repo.create("x")
    deleted = repo.soft_delete(post.id)
    assert deleted is not None
    assert deleted.deleted_at is not None
    assert repo.get_by_id(post.id) is None
    assert repo.list_posts() == []
    assert repo.get_by_id(post.id, include_deleted=True) is not None


def test_soft_delete_idempotent_returns_none_second_time():
    repo = InMemoryPostRepository()
    post = repo.create("x")
    assert repo.soft_delete(post.id) is not None
    assert repo.soft_delete(post.id) is None


def test_name_reusable_after_soft_delete():
    repo = InMemoryPostRepository()
    first = repo.create("reuse")
    repo.soft_delete(first.id)
    second = repo.create("reuse")
    assert second.id != first.id
    assert repo.get_by_name("reuse") == second


def test_list_posts_include_deleted():
    repo = InMemoryPostRepository()
    a = repo.create("a")
    repo.soft_delete(a.id)
    repo.create("b")
    active = repo.list_posts(include_deleted=False)
    assert len(active) == 1
    assert active[0].name == "b"
    all_posts = repo.list_posts(include_deleted=True)
    assert len(all_posts) == 2


def test_update_returns_none_when_soft_deleted():
    repo = InMemoryPostRepository()
    post = repo.create("z")
    repo.soft_delete(post.id)
    assert repo.update(post.id, name="y") is None


def test_get_by_name_include_deleted_prefers_newest():
    repo = InMemoryPostRepository()
    old = repo.create("dup")
    repo.soft_delete(old.id)
    new = repo.create("dup")
    found = repo.get_by_name("dup", include_deleted=True)
    assert found is not None
    assert found.id == new.id


def test_create_with_fixed_post_id():
    repo = InMemoryPostRepository()
    pid = "00000000-0000-4000-8000-000000000001"
    post = repo.create("x", post_id=pid, image_urls=[])
    assert post.id == pid


def test_create_uses_explicit_listings_when_provided():
    repo = InMemoryPostRepository()
    now = datetime.now(timezone.utc)
    listing = Listing(
        id="listing-123",
        marketplace_url="https://www.ebay.com/itm/listing-123",
        image_url="posts/p1/a.jpg",
        created_at=now,
        status="PUBLISHED",
        description="Published listing",
    )
    post = repo.create("explicit", image_urls=["posts/p1/a.jpg"], listings=[listing])
    assert post.listings == [listing]


def test_replace_listings_swaps_placeholder_listing():
    repo = InMemoryPostRepository()
    post = repo.create("replace", image_urls=["posts/p1/a.jpg"])
    assert len(post.listings) == 1
    replacement = Listing(
        id="listing-999",
        marketplace_url="https://www.ebay.com/itm/listing-999",
        image_url="posts/p1/a.jpg",
        created_at=datetime.now(timezone.utc),
        status="PUBLISHED",
        description="eBay listing",
    )
    updated = repo.replace_listings(post.id, [replacement])
    assert updated is not None
    assert updated.listings == [replacement]
