import type { Episode } from "../../types";

interface EpisodeButtonProps {
  episode: Episode;
  isActive?: boolean;
  onSelect: (episode: Episode) => void;
}

export function EpisodeButton({ episode, isActive, onSelect }: EpisodeButtonProps) {
  return (
    <button
      type="button"
      className={`episode-button ${isActive ? "active" : ""}`.trim()}
      onClick={() => onSelect(episode)}
      title={episode.title ?? `Episode ${episode.episode_number}`}
    >
      {episode.episode_number}
    </button>
  );
}

interface EpisodeSelectorProps {
  episodes: Episode[];
  activeEpisodeId?: string;
  onSelect: (episode: Episode) => void;
}

export function EpisodeSelector({ episodes, activeEpisodeId, onSelect }: EpisodeSelectorProps) {
  return (
    <div className="episode-grid">
      {episodes.map((episode) => (
        <EpisodeButton
          key={episode.id}
          episode={episode}
          isActive={episode.id === activeEpisodeId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
