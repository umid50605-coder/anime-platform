import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EpisodeSelector } from "../../components/anime/EpisodeSelector";
import { GenreChip } from "../../components/anime/GenreChip";
import { SecondaryButton } from "../../components/common/Button";
import { ErrorNotice, Loading } from "../../components/common/Status";
import { useAuth } from "../../features/auth/useAuth";
import { useFavorites } from "../../features/favorites/useFavorites";
import { fetchAnimeBySlug } from "../../services/api/anime";
import { fetchEpisodesForAnime } from "../../services/api/episodes";
import type { AnimeDetail, Episode } from "../../types";

export function AnimeDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { isFavorite, toggleFavorite } = useFavorites(!!user);

  const [anime, setAnime] = useState<AnimeDetail | null>(null);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    setAnime(null);
    setError(null);
    fetchAnimeBySlug(slug)
      .then((detail) => {
        setAnime(detail);
        return fetchEpisodesForAnime(detail.id);
      })
      .then(setEpisodes)
      .catch(() => setError("This title could not be found."));
  }, [slug]);

  if (error) {
    return (
      <div className="container page">
        <ErrorNotice message={error} />
      </div>
    );
  }

  if (!anime) {
    return (
      <div className="container page">
        <Loading />
      </div>
    );
  }

  const firstEpisode = episodes[0];

  return (
    <div>
      <section className="hero" style={{ minHeight: "clamp(280px, 42vh, 420px)" }}>
        {anime.poster_url && (
          <div className="hero-backdrop" style={{ backgroundImage: `url(${anime.poster_url})` }} />
        )}
        <div className="hero-scrim" />
      </section>

      <div className="container" style={{ marginTop: "-8rem", position: "relative", zIndex: 2 }}>
        <div className="row" style={{ alignItems: "flex-end", gap: "2rem", flexWrap: "wrap" }}>
          {anime.poster_url && (
            <img
              src={anime.poster_url}
              alt={anime.title}
              className="card"
              style={{ width: 200, aspectRatio: "2 / 3", objectFit: "cover", flexShrink: 0 }}
            />
          )}
          <div className="stack fade-in" style={{ flex: 1, minWidth: 260, paddingBottom: "0.5rem" }}>
            <h1 style={{ textTransform: "none" }}>{anime.title}</h1>
            <div className="row" style={{ flexWrap: "wrap" }}>
              {anime.genres.map((genre) => (
                <GenreChip key={genre} label={genre} />
              ))}
            </div>
          </div>
        </div>

        <div className="page" style={{ paddingTop: "var(--space-4)" }}>
          <div className="row" style={{ alignItems: "flex-start", gap: "var(--space-6)", flexWrap: "wrap" }}>
            <div className="stack" style={{ flex: "2 1 420px", minWidth: 280 }}>
              {anime.synopsis && <p>{anime.synopsis}</p>}

              <div className="row" style={{ flexWrap: "wrap" }}>
                {firstEpisode ? (
                  <Link to={`/watch/${firstEpisode.id}`} className="btn btn-primary">
                    ▶ Watch episode {firstEpisode.episode_number}
                  </Link>
                ) : (
                  <span className="status-line">No episodes available yet.</span>
                )}
                {user && (
                  <SecondaryButton onClick={() => toggleFavorite(anime.id)}>
                    {isFavorite(anime.id) ? "★ In favorites" : "☆ Add to favorites"}
                  </SecondaryButton>
                )}
              </div>
            </div>

            <div className="stack" style={{ flex: "1 1 260px", minWidth: 260 }}>
              <h2>Episodes</h2>
              <p className="status-line" style={{ marginTop: "-0.5rem" }}>
                {episodes.length} episode{episodes.length === 1 ? "" : "s"}
              </p>
              <EpisodeSelector episodes={episodes} onSelect={(ep) => navigate(`/watch/${ep.id}`)} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
