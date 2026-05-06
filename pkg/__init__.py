"""Reusable cloud client wrappers (storage, Firestore with Mongo-style API, Gemini)."""

from pkg.config import CloudSettings
from pkg.ebay_tokens import EbayTokenRepository, EbayUserToken, InMemoryEbayTokenRepository, MongoEbayTokenRepository
from pkg.firestore_mongo import FirestoreMongoDatabase
from pkg.gcs import GoogleCloudStorage
from pkg.gemini import GeminiClient
from pkg.logging_context import (
    REQUEST_ID_HEADER,
    configure_logging,
    get_logger,
    get_request_id,
    new_request_id,
    reset_request_id,
    set_request_id,
)
from pkg.posts import InMemoryPostRepository, MongoPostRepository, Post, PostRepository

__all__ = [
    "CloudSettings",
    "EbayTokenRepository",
    "EbayUserToken",
    "FirestoreMongoDatabase",
    "GeminiClient",
    "GoogleCloudStorage",
    "InMemoryEbayTokenRepository",
    "InMemoryPostRepository",
    "MongoEbayTokenRepository",
    "MongoPostRepository",
    "Post",
    "PostRepository",
    "REQUEST_ID_HEADER",
    "configure_logging",
    "get_logger",
    "get_request_id",
    "new_request_id",
    "reset_request_id",
    "set_request_id",
]
