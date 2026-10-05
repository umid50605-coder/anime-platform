import { apiClient } from "./client";
import type { AuthToken, User } from "../../types";

export interface RegisterPayload {
  email: string;
  password: string;
  display_name?: string;
}

export function register(payload: RegisterPayload): Promise<User> {
  return apiClient.post<User>("/api/auth/register", payload);
}

export function login(email: string, password: string): Promise<AuthToken> {
  return apiClient.post<AuthToken>(
    "/api/auth/login",
    { username: email, password },
    /* form */ true,
  );
}

export function fetchMe(): Promise<User> {
  return apiClient.get<User>("/api/users/me");
}
