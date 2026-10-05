import { useEffect, useState } from "react";
import { fetchHistory } from "../../services/api/watch";
import type { WatchHistoryEntry } from "../../types";

export function useWatchHistory(enabled: boolean) {
  const [history, setHistory] = useState<WatchHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    setIsLoading(true);
    fetchHistory()
      .then(setHistory)
      .finally(() => setIsLoading(false));
  }, [enabled]);

  return { history, isLoading };
}
