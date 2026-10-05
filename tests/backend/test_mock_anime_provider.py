import pytest
from app.integrations.anime_api.mock_provider import MockAnimeProvider


@pytest.fixture()
def provider():
    return MockAnimeProvider()


def test_get_anime_returns_known_fixture(provider):
    anime = provider.get_anime("mock-1")
    assert anime.title == "Skybound Chronicles"
    assert anime.slug == "skybound-chronicles"


def test_get_anime_unknown_id_raises(provider):
    with pytest.raises(ValueError):
        provider.get_anime("does-not-exist")


def test_search_is_case_insensitive_substring_match(provider):
    results = provider.search_anime("NEON")
    assert len(results) == 1
    assert results[0].external_id == "mock-2"


def test_search_empty_query_returns_all(provider):
    results = provider.search_anime("")
    assert len(results) == 2


def test_list_episodes_returns_ordered_fixture(provider):
    episodes = provider.list_episodes("mock-1")
    assert [e.episode_number for e in episodes] == [1, 2]
