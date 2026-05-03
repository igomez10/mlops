from __future__ import annotations

from typing import TYPE_CHECKING

from google import genai

if TYPE_CHECKING:
    from pkg.config import CloudSettings


class GeminiClient:
    """Wrapper around the Google Gen AI SDK (`google-genai`) with injectable client for tests."""

    def __init__(
        self,
        model: str,
        *,
        client: genai.Client | None = None,
        project: str | None = None,
        location: str | None = None,
    ) -> None:
        if not model:
            raise ValueError("model is required")
        self._model = model
        if client is not None:
            self._client = client
        else:
            if not project or not location:
                raise ValueError("project and location are required for Gemini ADC auth")
            self._client = genai.Client(
                vertexai=True,
                project=project,
                location=location,
            )

    @classmethod
    def from_settings(cls, settings: CloudSettings) -> GeminiClient:
        if not settings.gcp_project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT (or GCP_PROJECT) is required for Gemini ADC auth")
        return cls(
            settings.gemini_model,
            project=settings.gcp_project_id,
            location=settings.vertex_location,
        )

    @property
    def model(self) -> str:
        return self._model

    def generate_text(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
        )
        text = getattr(response, "text", None)
        if text:
            return text
        return ""
