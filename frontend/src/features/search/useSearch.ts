import { useEffect, useState } from "react";
import { searchAnime } from "../../services/api/anime";
import type { AnimeSearchResult } from "../../types";

export function useSearch(query: string) {
  const [results, setResults] = useState<AnimeSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setError(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    const handle = setTimeout(() => {
      searchAnime(trimmed)
        .then(setResults)
        .catch(() => setError("Search failed. Is the backend running?"))
        .finally(() => setIsLoading(false));
    }, 300);
    return () => clearTimeout(handle);
  }, [query]);

  return { results, isLoading, error };
}
