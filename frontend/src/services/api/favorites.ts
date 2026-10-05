import { apiClient } from "./client";
import type { Favorite } from "../../types";

export function fetchFavorites(): Promise<Favorite[]> {
  return apiClient.get<Favorite[]>("/api/favorites/");
}

export function addFavorite(animeId: string): Promise<Favorite> {
  return apiClient.post<Favorite>("/api/favorites/", { anime_id: animeId });
}

export function removeFavorite(animeId: string): Promise<void> {
  return apiClient.delete<void>(`/api/favorites/${animeId}`);
}
