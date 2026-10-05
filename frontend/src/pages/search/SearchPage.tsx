import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AnimeGrid } from "../../components/anime/AnimeGrid";
import { SearchBar } from "../../components/common/SearchBar";
import { EmptyState, ErrorNotice, Loading } from "../../components/common/Status";
import { useSearch } from "../../features/search/useSearch";

export function SearchPage() {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const { results, isLoading, error } = useSearch(query);

  return (
    <div className="container page stack">
      <h1>Search</h1>
      <SearchBar value={query} onChange={setQuery} placeholder="Search anime titles…" />

      {isLoading && <Loading label="Searching…" />}
      {error && <ErrorNotice message={error} />}
      {!isLoading && !error && query.trim() && results.length === 0 && (
        <EmptyState message={`No matches for "${query.trim()}".`} />
      )}
      {!query.trim() && !isLoading && (
        <p className="status-line">Start typing to search the anime catalog.</p>
      )}

      {results.length > 0 && (
        <AnimeGrid
          items={results.map((r) => ({
            key: r.external_id,
            slug: r.slug,
            title: r.title,
            posterUrl: r.poster_url || null,
          }))}
        />
      )}
    </div>
  );
}
