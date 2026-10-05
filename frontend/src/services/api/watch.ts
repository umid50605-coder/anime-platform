import { apiClient } from "./client";
import type { StreamInfo, WatchHistoryEntry, WatchProgress } from "../../types";

export function fetchProgress(episodeId: string): Promise<WatchProgress> {
  return apiClient.get<WatchProgress>(`/api/watch/${episodeId}/progress`);
}

export function updateProgress(episodeId: string, positionSeconds: number): Promise<WatchProgress> {
  return apiClient.put<WatchProgress>(`/api/watch/${episodeId}/progress`, {
    position_seconds: positionSeconds,
  });
}

export function fetchHistory(): Promise<WatchHistoryEntry[]> {
  return apiClient.get<WatchHistoryEntry[]>("/api/watch/history");
}

export function fetchStream(episodeId: string): Promise<StreamInfo> {
  return apiClient.get<StreamInfo>(`/api/watch/${episodeId}/stream`);
}
