from app.integrations.anime_api import AnimeProvider
from app.models.episode import Episode
from app.repositories.anime import AnimeRepository
from app.repositories.episode import EpisodeRepository


class AnimeNotFoundError(Exception):
    pass


class EpisodeService:
    def __init__(
        self,
        episode_repository: EpisodeRepository,
        anime_repository: AnimeRepository,
        anime_provider: AnimeProvider,
    ):
        self.episode_repository = episode_repository
        self.anime_repository = anime_repository
        self.anime_provider = anime_provider

    def list_for_anime(self, anime_id: str) -> list[Episode]:
        return self.episode_repository.list_for_anime(anime_id)

    def get_by_id(self, episode_id: str) -> Episode | None:
        return self.episode_repository.get_by_id(episode_id)

    def import_episodes_from_provider(self, anime_id: str) -> list[Episode]:
        """
        Syncs episode mappings for `anime_id` from the configured
        AnimeProvider. Existing episodes (matched by external_episode_id)
        are left untouched; only missing ones are created.
        """
        anime = self.anime_repository.get_by_id(anime_id)
        if anime is None:
            raise AnimeNotFoundError(f"Anime {anime_id} not found")

        episodes: list[Episode] = []
        for ep_meta in self.anime_provider.list_episodes(anime.external_id):
            existing = self.episode_repository.get_by_external_id(
                anime_id, ep_meta.external_episode_id
            )
            if existing is not None:
                episodes.append(existing)
                continue
            episode = Episode(
                anime_id=anime_id,
                external_episode_id=ep_meta.external_episode_id,
                episode_number=ep_meta.episode_number,
                title=ep_meta.title,
            )
            episodes.append(self.episode_repository.create(episode))
        return episodes
