import { useEffect, useState } from "react";
import { AnimeGrid } from "../../components/anime/AnimeGrid";
import { EmptyState, ErrorNotice, Loading } from "../../components/common/Status";
import { useAuth } from "../../features/auth/useAuth";
import { useFavorites } from "../../features/favorites/useFavorites";
import { fetchCatalog } from "../../services/api/anime";
import type { Anime } from "../../types";

export function FavoritesPage() {
  const { user } = useAuth();
  const { favorites, isLoading } = useFavorites(!!user);
  const [animeById, setAnimeById] = useState<Record<string, Anime>>({});

  useEffect(() => {
    if (!user) return;
    // Favorites only carry anime_id, not display fields - resolve against the
    // catalog rather than adding a per-id backend endpoint for this one view.
    fetchCatalog().then((catalog) => {
      setAnimeById(Object.fromEntries(catalog.map((a) => [a.id, a])));
    });
  }, [user]);

  if (!user) {
    return (
      <div className="container page">
        <h1>Favorites</h1>
        <ErrorNotice message="Sign in to see your favorites." />
      </div>
    );
  }

  const items = favorites
    .map((fav) => animeById[fav.anime_id])
    .filter((a): a is Anime => Boolean(a))
    .map((a) => ({ key: a.id, slug: a.slug, title: a.title, posterUrl: a.poster_url }));

  return (
    <div className="container page stack">
      <h1>Favorites</h1>
      {isLoading && <Loading />}
      {!isLoading && favorites.length === 0 && (
        <EmptyState message="You haven't favorited anything yet." />
      )}
      {items.length > 0 && <AnimeGrid items={items} />}
    </div>
  );
}
