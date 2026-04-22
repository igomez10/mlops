"""Reusable cloud client wrappers (storage, Firestore with Mongo-style API, Gemini)."""

from pkg.config import CloudSettings
from pkg.firestore_mongo import FirestoreMongoDatabase
from pkg.gcs import GoogleCloudStorage
from pkg.gemini import GeminiClient
from pkg.posts import InMemoryPostRepository, MongoPostRepository, Post, PostRepository

__all__ = [
    "CloudSettings",
    "FirestoreMongoDatabase",
    "GeminiClient",
    "GoogleCloudStorage",
    "InMemoryPostRepository",
    "MongoPostRepository",
    "Post",
    "PostRepository",
]
