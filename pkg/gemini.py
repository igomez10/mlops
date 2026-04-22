from __future__ import annotations

import os
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
        api_key: str | None = None,
        vertexai: bool = False,
        project: str | None = None,
        location: str | None = None,
    ) -> None:
        if not model:
            raise ValueError("model is required")
        self._model = model
        if client is not None:
            self._client = client
        elif vertexai:
            if not project or not location:
                raise ValueError("project and location are required when vertexai=True")
            self._client = genai.Client(
                vertexai=True,
                project=project,
                location=location,
            )
        else:
            key = api_key or os.environ.get("GEMINI_API_KEY")
            if not key:
                raise ValueError(
                    "Gemini API key is required (pass api_key or set GEMINI_API_KEY)"
                )
            self._client = genai.Client(api_key=key)

    @classmethod
    def from_settings(cls, settings: CloudSettings) -> GeminiClient:
        if settings.gemini_use_vertex:
            if not settings.gcp_project_id:
                raise ValueError(
                    "GOOGLE_CLOUD_PROJECT (or GCP_PROJECT) is required when GEMINI_USE_VERTEX is true"
                )
            return cls(
                settings.gemini_model,
                vertexai=True,
                project=settings.gcp_project_id,
                location=settings.vertex_location,
            )
        return cls(settings.gemini_model, api_key=settings.gemini_api_key)

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
