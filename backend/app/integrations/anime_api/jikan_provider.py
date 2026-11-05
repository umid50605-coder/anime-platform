"""Jikan (MyAnimeList) adapter.

Jikan is a public, read-only API and is used only when explicitly selected
through ``ANIME_PROVIDER=jikan``. All response-shape handling stays here so
the application receives the same vendor-neutral dataclasses as the mock.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.integrations.anime_api.provider import AnimeMetadata, AnimeProvider, EpisodeMetadata


class AnimeProviderError(RuntimeError):
    """Raised when an external anime provider cannot satisfy a request."""


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


class JikanAnimeProvider(AnimeProvider):
    name = "jikan"

    def __init__(self, base_url: str, timeout: float = 10.0):
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or parsed.hostname not in {"api.jikan.moe"}:
            raise ValueError("anime provider base URL must be https://api.jikan.moe")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = httpx.get(
                f"{self.base_url}/{path.lstrip('/')}", params=params, timeout=self.timeout
            )
        except httpx.TimeoutException as exc:
            raise AnimeProviderError("anime provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise AnimeProviderError("anime provider request failed") from exc
        if response.status_code == 429:
            raise AnimeProviderError("anime provider rate limit exceeded")
        if response.is_error:
            raise AnimeProviderError(f"anime provider returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise AnimeProviderError("anime provider returned invalid JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), (dict, list)):
            raise AnimeProviderError("anime provider returned an invalid response")
        return payload

    @staticmethod
    def _normalize(item: dict[str, Any]) -> AnimeMetadata:
        title = _text(item.get("title")) or _text(item.get("title_english"))
        if not title or not item.get("mal_id"):
            raise AnimeProviderError("anime provider returned incomplete anime data")
        images = item.get("images") or {}
        jpg = images.get("jpg") if isinstance(images, dict) else {}
        return AnimeMetadata(
            external_id=str(item["mal_id"]),
            title=title,
            slug=f"mal-{item['mal_id']}",
            poster_url=_text(jpg.get("image_url")) if isinstance(jpg, dict) else "",
            cover_url=_text(jpg.get("large_image_url")) if isinstance(jpg, dict) else "",
            synopsis=_text(item.get("synopsis")),
            genres=[
                _text(genre.get("name"))
                for genre in item.get("genres", [])
                if isinstance(genre, dict) and _text(genre.get("name"))
            ],
            alternative_titles=[
                value
                for value in (
                    item.get("title_english"),
                    item.get("title_japanese"),
                )
                if isinstance(value, str) and value.strip()
            ],
            release_year=item.get("year") if isinstance(item.get("year"), int) else None,
            status=_text(item.get("status")) or None,
        )

    def get_anime(self, external_id: str) -> AnimeMetadata:
        payload = self._get(f"anime/{external_id}/full")
        data = payload["data"]
        if not isinstance(data, dict):
            raise AnimeProviderError("anime provider returned an invalid anime")
        return self._normalize(data)

    def search_anime(self, query: str) -> list[AnimeMetadata]:
        payload = self._get("anime", {"q": query, "limit": 25})
        return [self._normalize(item) for item in payload["data"] if isinstance(item, dict)]

    def list_anime(self, page: int = 1, limit: int = 25) -> list[AnimeMetadata]:
        payload = self._get("anime", {"page": page, "limit": min(limit, 25)})
        return [self._normalize(item) for item in payload["data"] if isinstance(item, dict)]

    def list_episodes(self, external_id: str) -> list[EpisodeMetadata]:
        payload = self._get(f"anime/{external_id}/episodes", {"limit": 100})
        episodes: list[EpisodeMetadata] = []
        for item in payload["data"]:
            if not isinstance(item, dict) or not item.get("mal_id"):
                continue
            number = item.get("mal_id")
            episodes.append(
                EpisodeMetadata(
                    external_episode_id=str(item["mal_id"]),
                    episode_number=int(item.get("episode", number)),
                    title=_text(item.get("title")),
                )
            )
        return episodes


def get_jikan_provider() -> JikanAnimeProvider:
    settings = get_settings()
    return JikanAnimeProvider(
        settings.anime_provider_base_url, settings.anime_provider_timeout_seconds
    )
