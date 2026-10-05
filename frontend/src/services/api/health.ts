import { apiClient } from "./client";
import type { HealthStatus } from "../../types";

export function fetchHealth(): Promise<HealthStatus> {
  return apiClient.get<HealthStatus>("/health");
}
