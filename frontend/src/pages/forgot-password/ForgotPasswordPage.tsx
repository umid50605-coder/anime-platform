import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { PrimaryButton } from "../../components/common/Button";
import { ErrorNotice } from "../../components/common/Status";
import {
  GENERIC_ERROR_MESSAGE,
  RATE_LIMITED_MESSAGE,
} from "../../features/auth/passwordResetMessages";
import { requestPasswordReset } from "../../services/api/auth";
import { ApiError } from "../../services/api/client";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // State updates are asynchronous: a fast double-click can fire a second submit
  // before the disabled button has re-rendered. The ref closes that gap.
  const inFlight = useRef(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (inFlight.current) return;
    inFlight.current = true;
    setError(null);
    setIsSubmitting(true);
    try {
      // The server answers identically whether or not the address is registered,
      // and so does this page - it never says which.
      const { detail } = await requestPasswordReset(email.trim());
      setConfirmation(detail);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError(RATE_LIMITED_MESSAGE);
      } else if (err instanceof ApiError && err.status === 422) {
        setError("Enter a valid email address.");
      } else {
        setError(GENERIC_ERROR_MESSAGE);
      }
    } finally {
      inFlight.current = false;
      setIsSubmitting(false);
    }
  };

  if (confirmation) {
    return (
      <div className="container page stack">
        <h1>Check your email</h1>
        <p role="status">{confirmation}</p>
        <p className="status-line">The link expires soon and can be used once.</p>
        <Link to="/profile">Back to sign in</Link>
      </div>
    );
  }

  return (
    <div className="container page">
      <h1>Forgot password</h1>
      <form onSubmit={handleSubmit} className="stack" style={{ maxWidth: 360 }}>
        <p>Enter your account email and we will send you a link to choose a new password.</p>
        <div className="field">
          <label htmlFor="forgot-email">Email</label>
          <input
            id="forgot-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        {error && <ErrorNotice message={error} />}

        <PrimaryButton type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Sending…" : "Send reset link"}
        </PrimaryButton>
        <Link to="/profile">Back to sign in</Link>
      </form>
    </div>
  );
}
