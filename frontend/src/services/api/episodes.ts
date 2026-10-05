import { apiClient } from "./client";
import type { Episode } from "../../types";

export function fetchEpisodesForAnime(animeId: string): Promise<Episode[]> {
  return apiClient.get<Episode[]>(`/api/episodes/anime/${animeId}`);
}

export function fetchEpisode(episodeId: string): Promise<Episode> {
  return apiClient.get<Episode>(`/api/episodes/${episodeId}`);
}
