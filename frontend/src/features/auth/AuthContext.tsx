import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { fetchMe, login as apiLogin, register as apiRegister } from "../../services/api/auth";
import { setAuthToken } from "../../services/api/client";
import type { User } from "../../types";
import { AuthContext, TOKEN_STORAGE_KEY } from "./context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!storedToken) {
      setIsLoading(false);
      return;
    }
    setAuthToken(storedToken);
    fetchMe()
      .then(setUser)
      .catch(() => {
        // Stored token is no longer valid - clear it rather than staying "logged in"
        // with a token that will fail every request.
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        setAuthToken(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await apiLogin(email, password);
    localStorage.setItem(TOKEN_STORAGE_KEY, access_token);
    setAuthToken(access_token);
    setUser(await fetchMe());
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName?: string) => {
      await apiRegister({ email, password, display_name: displayName });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setAuthToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
