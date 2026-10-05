import { useCallback, useEffect, useState } from "react";
import { fetchProgress, updateProgress } from "../../services/api/watch";
import { ApiError } from "../../services/api/client";

export function useWatchProgress(episodeId: string | undefined) {
  const [positionSeconds, setPositionSeconds] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // No episodeId is passed for anonymous viewers (see WatchPage) - there's
    // no progress to load, and isLoading must still resolve to false or the
    // player would stay stuck on a loading state forever.
    if (!episodeId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    fetchProgress(episodeId)
      .then((p) => setPositionSeconds(p.position_seconds))
      .catch((err) => {
        // No progress yet is expected (404) - anything else, surface later if needed.
        if (!(err instanceof ApiError && err.status === 404)) {
          console.error(err);
        }
      })
      .finally(() => setIsLoading(false));
  }, [episodeId]);

  const saveProgress = useCallback(
    async (seconds: number) => {
      if (!episodeId) return;
      const updated = await updateProgress(episodeId, seconds);
      setPositionSeconds(updated.position_seconds);
    },
    [episodeId],
  );

  return { positionSeconds, isLoading, saveProgress };
}
