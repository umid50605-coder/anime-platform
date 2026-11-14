import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { PrimaryButton } from "../../components/common/Button";
import { ErrorNotice } from "../../components/common/Status";
import { useAuth } from "../../features/auth/useAuth";
import {
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH,
} from "../../features/auth/passwordPolicy";
import {
  GENERIC_ERROR_MESSAGE,
  RATE_LIMITED_MESSAGE,
} from "../../features/auth/passwordResetMessages";
import { resetPassword } from "../../services/api/auth";
import { ApiError } from "../../services/api/client";

// The emailed link is `/reset-password#token=...`. A URL fragment is never sent
// to any server, so the token stays out of access logs and Referer headers.
function readTokenFromFragment(): string {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  return params.get("token") ?? "";
}

export function ResetPasswordPage() {
  const { logout } = useAuth();
  // Held in component state only - never localStorage/sessionStorage/cookies.
  const [token, setToken] = useState(readTokenFromFragment);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const inFlight = useRef(false);

  useEffect(() => {
    // Take the token out of the address bar and the history entry right away,
    // so it is not left sitting in the URL, a bookmark, or a shared screenshot.
    if (window.location.hash) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (inFlight.current) return;

    if (password.length < MIN_PASSWORD_LENGTH || password.length > MAX_PASSWORD_LENGTH) {
      setError(
        `Choose a password between ${MIN_PASSWORD_LENGTH} and ${MAX_PASSWORD_LENGTH} characters.`,
      );
      return;
    }
    if (password !== confirmPassword) {
      setError("The two passwords do not match.");
      return;
    }

    inFlight.current = true;
    setError(null);
    setIsSubmitting(true);
    try {
      await resetPassword(token, password);
      // Spent: drop everything sensitive from memory and from the form.
      setToken("");
      setPassword("");
      setConfirmPassword("");
      setIsDone(true);
      // The server just revoked every session for this account. If this browser
      // was signed in, clear that stale local state rather than wait for a 401.
      void logout();
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        // One message for unknown, expired and already-used links alike.
        setError("This reset link is invalid or has expired. Please request a new one.");
      } else if (err instanceof ApiError && err.status === 429) {
        setError(RATE_LIMITED_MESSAGE);
      } else if (err instanceof ApiError && err.status === 422) {
        setError(
          `Choose a password between ${MIN_PASSWORD_LENGTH} and ${MAX_PASSWORD_LENGTH} characters.`,
        );
      } else {
        setError(GENERIC_ERROR_MESSAGE);
      }
    } finally {
      inFlight.current = false;
      setIsSubmitting(false);
    }
  };

  if (isDone) {
    return (
      <div className="container page stack">
        <h1>Password updated</h1>
        <p role="status">Your password has been reset. Sign in with your new password.</p>
        <Link to="/profile">Go to sign in</Link>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="container page stack">
        <h1>Reset link problem</h1>
        <ErrorNotice message="This reset link is missing or incomplete." />
        <Link to="/forgot-password">Request a new reset link</Link>
      </div>
    );
  }

  return (
    <div className="container page">
      <h1>Choose a new password</h1>
      <form onSubmit={handleSubmit} className="stack" style={{ maxWidth: 360 }}>
        <div className="field">
          <label htmlFor="new-password">New password</label>
          <input
            id="new-password"
            type="password"
            required
            autoComplete="new-password"
            minLength={MIN_PASSWORD_LENGTH}
            maxLength={MAX_PASSWORD_LENGTH}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="confirm-password">Confirm new password</label>
          <input
            id="confirm-password"
            type="password"
            required
            autoComplete="new-password"
            minLength={MIN_PASSWORD_LENGTH}
            maxLength={MAX_PASSWORD_LENGTH}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
        </div>

        {error && <ErrorNotice message={error} />}

        <PrimaryButton type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : "Reset password"}
        </PrimaryButton>
        {error?.includes("invalid or has expired") && (
          <Link to="/forgot-password">Request a new reset link</Link>
        )}
      </form>
    </div>
  );
}
