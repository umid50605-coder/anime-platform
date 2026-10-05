import { useState } from "react";
import type { FormEvent } from "react";
import { PrimaryButton, SecondaryButton } from "../../components/common/Button";
import { ErrorNotice } from "../../components/common/Status";
import { useAuth } from "../../features/auth/useAuth";
import { ApiError } from "../../services/api/client";

export function ProfilePage() {
  const { user, login, register, logout } = useAuth();

  if (user) {
    return (
      <div className="container page stack">
        <h1>Profile</h1>
        <p>{user.display_name || user.email}</p>
        <p className="status-line">{user.email}</p>
        <SecondaryButton style={{ alignSelf: "flex-start" }} onClick={logout}>
          Sign out
        </SecondaryButton>
      </div>
    );
  }

  return (
    <div className="container page">
      <h1>Sign in</h1>
      <AuthForms onLogin={login} onRegister={register} />
    </div>
  );
}

function AuthForms({
  onLogin,
  onRegister,
}: {
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string, displayName?: string) => Promise<void>;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      if (mode === "login") {
        await onLogin(email, password);
      } else {
        await onRegister(email, password, displayName || undefined);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="stack" style={{ maxWidth: 360 }}>
      {mode === "register" && (
        <div className="field">
          <label htmlFor="display-name">Display name</label>
          <input
            id="display-name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </div>
      )}
      <div className="field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      {error && <ErrorNotice message={error} />}

      <PrimaryButton type="submit" disabled={isSubmitting}>
        {mode === "login" ? "Sign in" : "Create account"}
      </PrimaryButton>

      <SecondaryButton
        type="button"
        onClick={() => setMode(mode === "login" ? "register" : "login")}
      >
        {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
      </SecondaryButton>
    </form>
  );
}
