import { useEffect, useRef, useState } from "react";
import { SecondaryButton } from "../../components/common/Button";
import { ErrorNotice } from "../../components/common/Status";
import { resendVerification } from "../../services/api/auth";
import { ApiError } from "../../services/api/client";
import { RESEND_COOLDOWN_SECONDS, VERIFY_GENERIC_ERROR_MESSAGE } from "./verificationMessages";

/**
 * "Send the verification email again" button for one known address.
 * Duplicate-submit protection: an in-flight ref (state updates are async) plus a
 * cooldown that mirrors the server's per-account cooldown. The server answers
 * the same way for every address, so the confirmation never says more than that.
 */
export function ResendVerification({ email }: { email: string }) {
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const inFlight = useRef(false);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  const handleClick = async () => {
    if (inFlight.current || cooldown > 0) return;
    inFlight.current = true;
    setError(null);
    setIsSending(true);
    try {
      const { detail } = await resendVerification(email);
      setMessage(detail);
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      setMessage(null);
      if (err instanceof ApiError && err.status === 429) {
        setError("Too many requests. Please wait a minute and try again.");
        setCooldown(RESEND_COOLDOWN_SECONDS);
      } else {
        setError(VERIFY_GENERIC_ERROR_MESSAGE);
      }
    } finally {
      inFlight.current = false;
      setIsSending(false);
    }
  };

  return (
    <div className="stack">
      <SecondaryButton
        type="button"
        style={{ alignSelf: "flex-start" }}
        disabled={isSending || cooldown > 0}
        onClick={handleClick}
      >
        {isSending
          ? "Sending…"
          : cooldown > 0
            ? `Send again in ${cooldown}s`
            : "Resend verification email"}
      </SecondaryButton>
      {message && <p role="status">{message}</p>}
      {error && <ErrorNotice message={error} />}
    </div>
  );
}
