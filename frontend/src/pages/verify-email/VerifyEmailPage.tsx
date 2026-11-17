import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorNotice, Loading } from "../../components/common/Status";
import { useAuth } from "../../features/auth/useAuth";
import {
  VERIFY_GENERIC_ERROR_MESSAGE,
  VERIFY_RATE_LIMITED_MESSAGE,
} from "../../features/auth/verificationMessages";
import { verifyEmail } from "../../services/api/auth";
import { ApiError } from "../../services/api/client";

type State =
  | { kind: "verifying" }
  | { kind: "success" }
  | { kind: "missing" }
  | { kind: "invalid" }
  | { kind: "error"; message: string };

// The emailed link is `/verify-email#token=...`. A URL fragment is never sent to
// a server, so the token stays out of access logs and Referer headers.
function readTokenFromFragment(): string {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  return params.get("token") ?? "";
}

export function VerifyEmailPage() {
  const { user, refreshUser } = useAuth();
  // Held in component state only - never localStorage/sessionStorage/cookies.
  const [token] = useState(readTokenFromFragment);
  const [state, setState] = useState<State>(token ? { kind: "verifying" } : { kind: "missing" });
  // A token is single-use: StrictMode's double effect (and re-renders) must not
  // submit it twice, or the second call would report "invalid" after a success.
  const started = useRef(false);

  useEffect(() => {
    // Take the token out of the address bar and history entry right away.
    if (window.location.hash) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    if (!token || started.current) return;
    started.current = true;
    verifyEmail(token)
      .then(() => {
        setState({ kind: "success" });
        void refreshUser(); // so a signed-in session immediately sees email_verified
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 400) {
          setState({ kind: "invalid" });
        } else if (err instanceof ApiError && err.status === 429) {
          setState({ kind: "error", message: VERIFY_RATE_LIMITED_MESSAGE });
        } else {
          setState({ kind: "error", message: VERIFY_GENERIC_ERROR_MESSAGE });
        }
      });
  }, [token, refreshUser]);

  return (
    <div className="container page stack">
      <h1>Verify email</h1>

      {state.kind === "verifying" && <Loading label="Verifying your email…" />}

      {state.kind === "success" && (
        <>
          <p role="status">Your email address has been verified.</p>
          <Link to="/profile">{user ? "Go to your profile" : "Continue to sign in"}</Link>
        </>
      )}

      {state.kind === "missing" && (
        <>
          <ErrorNotice message="This verification link is incomplete. Open the link from your email again." />
          <Link to="/profile">Back to sign in</Link>
        </>
      )}

      {state.kind === "invalid" && (
        <>
          <ErrorNotice message="This verification link is invalid, has expired, or was already used." />
          <p className="status-line">
            If you already verified your email, you can just sign in. Otherwise, sign in and
            request a new verification email from your profile.
          </p>
          <Link to="/profile">Go to sign in</Link>
        </>
      )}

      {state.kind === "error" && (
        <>
          <ErrorNotice message={state.message} />
          <Link to="/profile">Back to sign in</Link>
        </>
      )}
    </div>
  );
}
