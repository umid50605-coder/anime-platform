import { useEffect, useState } from "react";
import { fetchHealth } from "../services/api/health";

type ConnectionState = "checking" | "connected" | "unreachable";

export function useBackendHealth() {
  const [state, setState] = useState<ConnectionState>("checking");
  const [environment, setEnvironment] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((health) => {
        setState("connected");
        setEnvironment(health.environment);
      })
      .catch(() => setState("unreachable"));
  }, []);

  return { state, environment };
}
