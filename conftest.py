import sys
from pathlib import Path

import pytest
from docker.errors import DockerException
from testcontainers.mongodb import MongoDbContainer

sys.path.insert(0, str(Path(__file__).parent))


_ISOLATED_ENV_VARS = (
    "GOOGLE_CLOUD_PROJECT",
    "GCP_PROJECT",
    "GCLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "GCS_BUCKET",
    "GCS_IMAGES_BUCKET",
    "FIRESTORE_DATABASE_ID",
    "GEMINI_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_USE_VERTEX",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "MONGODB_URI",
    "MONGO_DATABASE",
    "POSTS_BACKEND",
    "MLFLOW_TRACKING_URI",
    "MLFLOW_TRACKING_ENABLED",
    "MLFLOW_EXPERIMENT_NAME",
    "MLFLOW_ARTIFACT_URI",
)


@pytest.fixture(autouse=True)
def isolate_env_from_dotenv(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep normal tests independent from .env / host shell config.

    Live tests are the exception: they intentionally exercise real external
    services and should keep the caller's environment.
    """
    if request.node.get_closest_marker("live") is not None:
        return
    for name in _ISOLATED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="session")
def mongo_container() -> MongoDbContainer:
    try:
        with MongoDbContainer("mongo:7") as mongo:
            yield mongo
    except DockerException as exc:
        pytest.skip(f"Docker unavailable for Mongo integration tests: {exc}")
