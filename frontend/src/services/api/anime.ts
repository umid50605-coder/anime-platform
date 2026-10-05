import { apiClient } from "./client";
import type { Anime, AnimeDetail, AnimeSearchResult } from "../../types";

export function fetchCatalog(): Promise<Anime[]> {
  return apiClient.get<Anime[]>("/api/anime/");
}

export function fetchAnimeBySlug(slug: string): Promise<AnimeDetail> {
  return apiClient.get<AnimeDetail>(`/api/anime/${slug}`);
}

export function searchAnime(query: string): Promise<AnimeSearchResult[]> {
  return apiClient.get<AnimeSearchResult[]>(`/api/search/?q=${encodeURIComponent(query)}`);
}
