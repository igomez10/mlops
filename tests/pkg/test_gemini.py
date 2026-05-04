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


def test_gemini_from_settings_requires_project(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)

    settings = CloudSettings(
        gcp_project_id=None,
        gcs_bucket=None,
        gcs_images_bucket=None,
        firestore_database_id="(default)",
        gemini_model="gem-m",
        vertex_location="us-central1",
        mongodb_uri=None,
        ebay_app_id=None,
        ebay_cert_id=None,
        ebay_sandbox=False,
    )
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
        GeminiClient.from_settings(settings)


def test_gemini_from_settings_uses_adc(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "proj-x")
    with patch_genai_client() as mock_cls:
        GeminiClient.from_settings(CloudSettings.from_env())
        mock_cls.assert_called_once_with(
            vertexai=True,
            project="proj-x",
            location="us-central1",
        )


def test_gemini_rejects_api_key_constructor() -> None:
    with pytest.raises(ValueError, match="API key auth is no longer supported"):
        GeminiClient("gemini-test", api_key="key-1")


def patch_genai_client():
    from unittest.mock import patch

    return patch("pkg.gemini.genai.Client")
