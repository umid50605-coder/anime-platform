import { createContext } from "react";
import type { User } from "../../types";

export const LEGACY_TOKEN_STORAGE_KEY = "anime_platform_token";

export interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
