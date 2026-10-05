"""
Guards the core requirement from the auth-removal change: browsing and
watching are fully public. If any of these endpoints ever start requiring
Authorization again, this test should fail loudly.
"""


def _seed_one_anime_with_episode(client):
    """
    Minimal seed via the service layer directly (no public "import" endpoint
    exists, by design - see AnimeService.import_from_provider) so tests don't
    depend on the mock provider's exact fixture data shape.
    """
    from app.core.database import get_db
    from app.integrations.anime_api import get_anime_provider
    from app.repositories.anime import AnimeRepository
    from app.repositories.episode import EpisodeRepository
    from app.services.anime import AnimeService
    from app.services.episode import EpisodeService

    db = next(client.app.dependency_overrides[get_db]())
    provider = get_anime_provider()
    anime = AnimeService(AnimeRepository(db), provider).import_from_provider("mock-1")
    episodes = EpisodeService(EpisodeRepository(db), AnimeRepository(db), provider)
    episodes.import_episodes_from_provider(anime.id)
    return anime


def test_full_public_flow_requires_no_authentication(client):
    anime = _seed_one_anime_with_episode(client)

    # Home -> catalog
    catalog_resp = client.get("/api/anime/")
    assert catalog_resp.status_code == 200
    assert any(a["id"] == anime.id for a in catalog_resp.json())

    # Anime -> detail
    detail_resp = client.get(f"/api/anime/{anime.slug}")
    assert detail_resp.status_code == 200

    # -> episodes
    episodes_resp = client.get(f"/api/episodes/anime/{anime.id}")
    assert episodes_resp.status_code == 200
    episode_id = episodes_resp.json()[0]["id"]

    # search
    search_resp = client.get("/api/search/?q=sky")
    assert search_resp.status_code == 200

    # -> watch (stream)
    stream_resp = client.get(f"/api/watch/{episode_id}/stream")
    assert stream_resp.status_code == 200
    assert "stream_url" in stream_resp.json()

    # None of the above should have required an Authorization header, and
    # none of them should have returned a 401/403.
    for resp in (catalog_resp, detail_resp, episodes_resp, search_resp, stream_resp):
        assert resp.status_code not in (401, 403)


def test_watch_progress_and_history_still_require_authentication(client):
    """
    These stay account-scoped on purpose (see PROJECT_RULES.md /
    ARCHITECTURE.md) - only /stream became public, not the whole watch module.
    """
    anime = _seed_one_anime_with_episode(client)
    episode_id = client.get(f"/api/episodes/anime/{anime.id}").json()[0]["id"]

    assert client.get(f"/api/watch/{episode_id}/progress").status_code == 401
    assert (
        client.put(f"/api/watch/{episode_id}/progress", json={"position_seconds": 10}).status_code
        == 401
    )
    assert client.get("/api/watch/history").status_code == 401


def test_health_endpoint_is_public(client):
    assert client.get("/health").status_code == 200


def test_watch_history_response_still_includes_resolved_anime_id(client):
    """
    Regression test for the API -> Service -> Repository layering fix:
    GET /api/watch/history used to assemble anime_id by having the router
    reach into `watch_service.watch_repository` directly. This exercises
    the endpoint end-to-end (register -> login -> record progress -> read
    history) through the real HTTP layer to confirm WatchService.
    list_history() now does that assembly itself and the response contract
    (episode_id/anime_id/position_seconds/updated_at) is unchanged.
    """
    anime = _seed_one_anime_with_episode(client)
    episode_id = client.get(f"/api/episodes/anime/{anime.id}").json()[0]["id"]

    client.post(
        "/api/auth/register",
        json={"email": "history-user@example.com", "password": "CorrectHorse123"},
    )
    login_resp = client.post(
        "/api/auth/login",
        data={"username": "history-user@example.com", "password": "CorrectHorse123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.put(f"/api/watch/{episode_id}/progress", json={"position_seconds": 42}, headers=headers)

    history_resp = client.get("/api/watch/history", headers=headers)
    assert history_resp.status_code == 200
    entries = history_resp.json()
    assert len(entries) == 1
    assert set(entries[0].keys()) == {"episode_id", "anime_id", "position_seconds", "updated_at"}
    assert entries[0]["episode_id"] == episode_id
    assert entries[0]["anime_id"] == anime.id
    assert entries[0]["position_seconds"] == 42


def test_watch_history_uses_empty_anime_id_when_episode_is_unresolvable(client):
    """
    Preserves existing behavior (not a new contract) for a history row whose
    episode can no longer be resolved: the router used to fall back to "",
    via `repo.get_anime_id_for_episode(...) or ""`. WatchService.list_history
    keeps that exact fallback - checked directly against the service here
    since provoking this through HTTP would require deleting an episode
    that still has progress recorded against it, which no endpoint does.
    """
    from app.core.database import get_db
    from app.repositories.episode import EpisodeRepository
    from app.repositories.watch import WatchRepository
    from app.services.watch import WatchService

    db = next(client.app.dependency_overrides[get_db]())
    watch_repository = WatchRepository(db)
    watch_repository.upsert_progress(
        user_id="user-with-orphaned-progress", episode_id="does-not-exist", position_seconds=5
    )

    from app.integrations.video_source import get_video_provider

    service = WatchService(watch_repository, EpisodeRepository(db), get_video_provider())
    history = service.list_history("user-with-orphaned-progress")

    assert len(history) == 1
    assert history[0].anime_id == ""
