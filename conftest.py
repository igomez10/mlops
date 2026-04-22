import sys
from pathlib import Path

import pytest
from testcontainers.mongodb import MongoDbContainer

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture(scope="session")
def mongo_container() -> MongoDbContainer:
    with MongoDbContainer("mongo:7") as mongo:
        yield mongo
