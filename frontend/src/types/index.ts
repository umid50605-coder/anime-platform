export interface User {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface Anime {
  id: string;
  slug: string;
  title: string;
  poster_url: string | null;
  created_at: string;
}

export interface AnimeDetail extends Anime {
  synopsis: string | null;
  genres: string[];
}

export interface AnimeSearchResult {
  external_id: string;
  title: string;
  slug: string;
  poster_url: string;
  synopsis: string;
  genres: string[];
}

export interface Episode {
  id: string;
  anime_id: string;
  episode_number: number;
  title: string | null;
}

export interface StreamInfo {
  stream_url: string;
  provider: string;
}

export interface WatchProgress {
  episode_id: string;
  position_seconds: number;
  updated_at: string;
}

export interface WatchHistoryEntry {
  episode_id: string;
  anime_id: string;
  position_seconds: number;
  updated_at: string;
}

export interface Favorite {
  id: string;
  anime_id: string;
  created_at: string;
}

export interface HealthStatus {
  status: string;
  environment: string;
}
