import { useCallback, useEffect, useState } from "react";
import { addFavorite, fetchFavorites, removeFavorite } from "../../services/api/favorites";
import type { Favorite } from "../../types";

export function useFavorites(enabled: boolean) {
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const reload = useCallback(() => {
    if (!enabled) return;
    setIsLoading(true);
    fetchFavorites()
      .then(setFavorites)
      .finally(() => setIsLoading(false));
  }, [enabled]);

  useEffect(() => {
    reload();
  }, [reload]);

  const isFavorite = useCallback(
    (animeId: string) => favorites.some((f) => f.anime_id === animeId),
    [favorites],
  );

  const toggleFavorite = useCallback(
    async (animeId: string) => {
      if (isFavorite(animeId)) {
        await removeFavorite(animeId);
      } else {
        await addFavorite(animeId);
      }
      reload();
    },
    [isFavorite, reload],
  );

  return { favorites, isLoading, isFavorite, toggleFavorite };
}
