import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { AnimeGrid } from "../../components/anime/AnimeGrid";
import { Hero } from "../../components/common/Hero";
import { SearchBar } from "../../components/common/SearchBar";
import { SectionHeader } from "../../components/common/SectionHeader";
import { EmptyState, ErrorNotice, Loading } from "../../components/common/Status";
import { useBackendHealth } from "../../hooks/useBackendHealth";
import { fetchCatalog } from "../../services/api/anime";
import type { Anime } from "../../types";

type QuickFilter = "all" | "newest";

export function HomePage() {
  const navigate = useNavigate();
  const { state, environment } = useBackendHealth();
  const [catalog, setCatalog] = useState<Anime[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [heroQuery, setHeroQuery] = useState("");
  const [filter, setFilter] = useState<QuickFilter>("all");

  useEffect(() => {
    fetchCatalog()
      .then(setCatalog)
      .catch(() => setError("Could not load the catalog. Is the backend running?"));
  }, []);

  const heroBackdrop = catalog?.find((a) => a.poster_url)?.poster_url ?? null;

  // "Trending" is the same real catalog, just a second, differently-ordered
  // view - there is no separate trending/popularity feed yet (see the final
  // report's Known limitations).
  const trending = useMemo(() => (catalog ? [...catalog].reverse() : []), [catalog]);

  const filtered = useMemo(() => {
    if (!catalog) return [];
    if (filter === "newest") {
      return [...catalog].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
    }
    return catalog;
  }, [catalog, filter]);

  const handleHeroSearch = (e: FormEvent) => {
    e.preventDefault();
    if (heroQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(heroQuery.trim())}`);
    }
  };

  const toGridItems = (list: Anime[]) =>
    list.map((a) => ({ key: a.id, slug: a.slug, title: a.title, posterUrl: a.poster_url }));

  return (
    <div>
      <Hero
        eyebrow={`Backend ${state}${environment ? ` · ${environment}` : ""}`}
        title="Chase the next arc"
        subtitle="Browse the catalog, pick an episode, and start watching — no account required."
        backgroundImage={heroBackdrop}
      >
        <form className="hero-search" onSubmit={handleHeroSearch}>
          <SearchBar
            id="hero-search"
            value={heroQuery}
            onChange={setHeroQuery}
            placeholder="Search for a title…"
          />
        </form>
        <div className="filter-row">
          <button
            type="button"
            className={`filter-chip ${filter === "all" ? "active" : ""}`}
            onClick={() => setFilter("all")}
          >
            All
          </button>
          <button
            type="button"
            className={`filter-chip ${filter === "newest" ? "active" : ""}`}
            onClick={() => setFilter("newest")}
          >
            Newest
          </button>
        </div>
      </Hero>

      <div className="container">
        <div className="section">
          <SectionHeader title={filter === "newest" ? "Newest additions" : "Full catalog"} />
          {error && <ErrorNotice message={error} />}
          {!error && catalog === null && <Loading label="Loading catalog…" />}
          {catalog && catalog.length === 0 && (
            <EmptyState message="The catalog is empty. Run scripts/seed_mock_data.py to add sample titles." />
          )}
          {catalog && catalog.length > 0 && <AnimeGrid items={toGridItems(filtered)} />}
        </div>

        {trending.length > 0 && (
          <div className="section">
            <SectionHeader title="Trending now" subtitle="What the community is watching" />
            <AnimeGrid items={toGridItems(trending)} />
          </div>
        )}
      </div>
    </div>
  );
}
