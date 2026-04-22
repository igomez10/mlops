from unittest.mock import MagicMock

import pytest

from pkg.config import CloudSettings
from pkg.gemini import GeminiClient


def test_gemini_requires_model():
    fake = MagicMock()
    with pytest.raises(ValueError, match="model"):
        GeminiClient("", client=fake)


def test_gemini_generate_text_uses_injected_client():
    response = MagicMock()
    response.text = "hello"

    models = MagicMock()
    models.generate_content.return_value = response

    client = MagicMock()
    client.models = models

    g = GeminiClient("gemini-test", client=client)
    assert g.model == "gemini-test"
    assert g.generate_text("ping") == "hello"
    models.generate_content.assert_called_once_with(
        model="gemini-test",
        contents="ping",
    )


def test_gemini_generate_text_empty_when_no_text():
    response = MagicMock()
    del response.text
    response.text = None

    models = MagicMock()
    models.generate_content.return_value = response
    client = MagicMock()
    client.models = models

    g = GeminiClient("m", client=client)
    assert g.generate_text("x") == ""


def test_gemini_from_settings_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.delenv("GEMINI_USE_VERTEX", raising=False)

    with patch_genai_client() as mock_cls:
        GeminiClient.from_settings(
            CloudSettings(
                gcp_project_id=None,
                gcs_bucket=None,
                gcs_images_bucket=None,
                firestore_database_id="(default)",
                gemini_model="gem-m",
                gemini_api_key="k",
                gemini_use_vertex=False,
                vertex_location="us-central1",
                mongodb_uri=None,
            )
        )
        mock_cls.assert_called_once_with(api_key="k")


def test_gemini_from_settings_vertex_requires_project(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    settings = CloudSettings(
        gcp_project_id=None,
        gcs_bucket=None,
        gcs_images_bucket=None,
        firestore_database_id="(default)",
        gemini_model="gem-m",
        gemini_api_key=None,
        gemini_use_vertex=True,
        vertex_location="us-central1",
        mongodb_uri=None,
    )
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
        GeminiClient.from_settings(settings)


def test_gemini_from_settings_vertex(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "proj-x")
    monkeypatch.setenv("GEMINI_USE_VERTEX", "true")

    with patch_genai_client() as mock_cls:
        GeminiClient.from_settings(CloudSettings.from_env())
        mock_cls.assert_called_once_with(
            vertexai=True,
            project="proj-x",
            location="us-central1",
        )


def patch_genai_client():
    from unittest.mock import patch

    return patch("pkg.gemini.genai.Client")
