import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EpisodeSelector } from "../../components/anime/EpisodeSelector";
import { VideoPlayerContainer } from "../../components/player/VideoPlayerContainer";
import { VideoPlayer } from "../../components/player/VideoPlayer";
import { SecondaryButton } from "../../components/common/Button";
import { ErrorNotice, Loading } from "../../components/common/Status";
import { useAuth } from "../../features/auth/useAuth";
import { useWatchProgress } from "../../features/watch-progress/useWatchProgress";
import { fetchCatalog } from "../../services/api/anime";
import { fetchEpisode, fetchEpisodesForAnime } from "../../services/api/episodes";
import { fetchStream } from "../../services/api/watch";
import { formatPosition } from "../../utils/formatPosition";
import type { Anime, Episode, StreamInfo } from "../../types";

const SAVE_INTERVAL_SECONDS = 10;

/**
 * Public page - no sign-in required to watch. Watch progress is a bonus for
 * signed-in users only (see useWatchProgress: passing `undefined` when there
 * is no user makes it a safe no-op, not an error).
 *
 * Episode context (title, selector, prev/next) is assembled client-side from
 * three existing, already-public endpoints (episode, episodes-for-anime,
 * catalog) - no backend changes were made for this page.
 */
export function WatchPage() {
  const { episodeId } = useParams<{ episodeId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { positionSeconds, isLoading, saveProgress } = useWatchProgress(
    user ? episodeId : undefined,
  );

  const [stream, setStream] = useState<StreamInfo | null>(null);
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [siblingEpisodes, setSiblingEpisodes] = useState<Episode[]>([]);
  const [anime, setAnime] = useState<Anime | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastSavedAtRef = useRef(0);

  useEffect(() => {
    if (!episodeId) return;
    setStream(null);
    setError(null);

    fetchStream(episodeId)
      .then(setStream)
      .catch(() => setError("Could not resolve a stream for this episode."));

    fetchEpisode(episodeId)
      .then((ep) => {
        setEpisode(ep);
        return Promise.all([fetchEpisodesForAnime(ep.anime_id), fetchCatalog()]);
      })
      .then(([episodes, catalog]) => {
        setSiblingEpisodes(episodes);
        setAnime(catalog.find((a) => a.id === episodes[0]?.anime_id) ?? null);
      })
      .catch(() => {
        /* episode context is a bonus (title/selector) - stream still plays without it */
      });
  }, [episodeId]);

  const handleProgress = useCallback(
    (seconds: number) => {
      if (!user) return;
      if (Math.abs(seconds - lastSavedAtRef.current) >= SAVE_INTERVAL_SECONDS) {
        lastSavedAtRef.current = seconds;
        saveProgress(seconds).catch(() => {
          /* best-effort - a missed progress save isn't worth surfacing to the user */
        });
      }
    },
    [saveProgress, user],
  );

  if (error) {
    return (
      <div className="container page">
        <ErrorNotice message={error} />
      </div>
    );
  }

  if (!stream || isLoading) {
    return (
      <div className="container page">
        <Loading label="Preparing playback…" />
      </div>
    );
  }

  const sortedEpisodes = [...siblingEpisodes].sort((a, b) => a.episode_number - b.episode_number);
  const currentIndex = sortedEpisodes.findIndex((e) => e.id === episodeId);
  const prevEpisode = currentIndex > 0 ? sortedEpisodes[currentIndex - 1] : null;
  const nextEpisode =
    currentIndex >= 0 && currentIndex < sortedEpisodes.length - 1
      ? sortedEpisodes[currentIndex + 1]
      : null;

  return (
    <div className="container page stack">
      <VideoPlayerContainer>
        <VideoPlayer
          src={stream.stream_url}
          startPositionSeconds={positionSeconds}
          onProgress={handleProgress}
        />
      </VideoPlayerContainer>

      <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
        <div>
          {anime && (
            <h2 style={{ marginBottom: "0.25rem" }}>
              <Link to={`/anime/${anime.slug}`}>{anime.title}</Link>
            </h2>
          )}
          {episode && (
            <p className="status-line" style={{ margin: 0 }}>
              Episode {episode.episode_number}
              {episode.title ? ` · ${episode.title}` : ""}
            </p>
          )}
          {user && <p className="status-line">Resuming from {formatPosition(positionSeconds)}</p>}
        </div>
        <div className="row">
          <SecondaryButton
            disabled={!prevEpisode}
            onClick={() => prevEpisode && navigate(`/watch/${prevEpisode.id}`)}
          >
            ← Previous
          </SecondaryButton>
          <SecondaryButton
            disabled={!nextEpisode}
            onClick={() => nextEpisode && navigate(`/watch/${nextEpisode.id}`)}
          >
            Next →
          </SecondaryButton>
        </div>
      </div>

      {sortedEpisodes.length > 1 && (
        <div>
          <h3>Episodes</h3>
          <EpisodeSelector
            episodes={sortedEpisodes}
            activeEpisodeId={episodeId}
            onSelect={(ep) => navigate(`/watch/${ep.id}`)}
          />
        </div>
      )}
    </div>
  );
}
