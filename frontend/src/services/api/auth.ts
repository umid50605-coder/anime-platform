import { apiClient, restoreAuthToken } from "./client";
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

export function refresh(): Promise<AuthToken> {
  return restoreAuthToken().then((access_token) => ({
    access_token,
    token_type: "bearer",
  }));
}

export function logout(): Promise<void> {
  return apiClient.post<void>("/api/auth/logout");
}

export function fetchMe(): Promise<User> {
  return apiClient.get<User>("/api/users/me");
}
