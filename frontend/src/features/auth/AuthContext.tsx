import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  fetchMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  refresh as apiRefresh,
} from "../../services/api/auth";
import {
  setAuthToken,
  setAuthenticationFailureHandler,
} from "../../services/api/client";
import type { User } from "../../types";
import { AuthContext, LEGACY_TOKEN_STORAGE_KEY } from "./context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const authOperationVersion = useRef(0);

  useEffect(() => {
    localStorage.removeItem(LEGACY_TOKEN_STORAGE_KEY);
    const operationVersion = authOperationVersion.current;
    const handleAuthenticationFailure = () => setUser(null);
    setAuthenticationFailureHandler(handleAuthenticationFailure);
    void apiRefresh()
      .then(fetchMe)
      .then((currentUser) => {
        if (operationVersion === authOperationVersion.current) {
          setUser(currentUser);
        }
      })
      .catch(() => {
        if (operationVersion === authOperationVersion.current) {
          setUser(null);
        }
      })
      .finally(() => setIsLoading(false));
    return () => setAuthenticationFailureHandler(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const operationVersion = ++authOperationVersion.current;
    setAuthToken(null);
    const { access_token } = await apiLogin(email, password);
    if (operationVersion !== authOperationVersion.current) {
      return;
    }
    setAuthToken(access_token);
    const currentUser = await fetchMe();
    if (operationVersion === authOperationVersion.current) {
      setUser(currentUser);
    }
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName?: string) => {
      await apiRegister({ email, password, display_name: displayName });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    ++authOperationVersion.current;
    localStorage.removeItem(LEGACY_TOKEN_STORAGE_KEY);
    setAuthToken(null);
    setUser(null);
    try {
      await apiLogout();
    } catch {
      // Local logout must complete even if the server cannot be reached.
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
