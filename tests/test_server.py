from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from server import CreatePostsRequest, app


@pytest.fixture
def mock_model():
    model = MagicMock()
    model.predict.return_value = [42000]
    return model


@pytest.fixture
def client(mock_model):
    with (
        patch("server.mlflow.set_tracking_uri"),
        patch("server.mlflow.pyfunc.load_model", return_value=mock_model),
        patch.dict(
            "os.environ",
            {
                "MLFLOW_TRACKING_URI": "http://localhost:5000",
                "MLFLOW_MODEL_NAME": "test_model",
            },
        ),
    ):
        with TestClient(app) as test_client:
            yield test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to mlops fastapi!"}


def test_usfca(client):
    response = client.get("/usfca")
    assert response.status_code == 200
    assert response.json() == "something"


def test_add_query_parameters(client):
    response = client.post("/add_query_parameters?num1=3&num2=4")
    assert response.status_code == 200
    assert response.json() == {"result": 7}


def test_add_body_parameters(client):
    response = client.post("/add_body_parameters", json={"num1": 1, "num2": 2})
    assert response.status_code == 200
    b0, b1, b2 = 27, 256, 339
    assert response.json() == {"result": b0 + b1 * 1 + b2 * 2}


def test_predict(client, mock_model):
    mock_model.predict.return_value: list[int] = [450000]
    response = client.post("/predict_price_sqft", json={"sqft": 1500, "rooms": 3})
    assert response.status_code == 200
    assert response.json() == {"prediction": 450000}


def test_create_valid_post_request():
    valid_request = CreatePostsRequest(
        dry_run=True,
        platform="ebay",
        user_estimated_price=50000,
        images=[b"123"],
        user_id=123,
    )

    assert valid_request.validate_request() is True


def test_create_invalid_post_request():
    invalid_request = CreatePostsRequest(
        dry_run=True,
        platform="ebay",
        user_estimated_price=50000,
        images=[b"123"],
        user_id=123,
    )

    # Missing required field 'platform'
    with pytest.raises(ValueError, match="Missing required field: platform"):
        invalid_request.validate_request()

    # Invalid platform value
    invalid_request.platform = "invalid_platform"
    with pytest.raises(ValueError, match="Invalid platform: invalid_platform"):
        invalid_request.validate_request()
