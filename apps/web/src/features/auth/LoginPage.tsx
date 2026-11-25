import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { isMfaRequired, useLogin, useLoginMfa } from "../../api/auth";
import { ErrorState } from "../../components/States";
import { AuthLayout } from "./AuthLayout";

type LocationState = { from?: string; registered?: boolean } | null;

/** Password sign-in, then a six-digit code when two-factor is on (POST /auth/login/mfa). */
export function LoginPage() {
  const navigate = useNavigate();
  const state = useLocation().state as LocationState;
  const login = useLogin();
  const mfa = useLoginMfa();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const done = () => navigate(state?.from ?? "/projects", { replace: true });

  const submitPassword = (e: FormEvent) => {
    e.preventDefault();
    login.mutate(
      { email, password },
      { onSuccess: (r) => (isMfaRequired(r) ? setMfaToken(r.mfa_token) : done()) },
    );
  };
  const submitCode = (e: FormEvent) => {
    e.preventDefault();
    if (mfaToken) mfa.mutate({ mfa_token: mfaToken, code: code.trim() }, { onSuccess: done });
  };

  if (mfaToken) {
    return (
      <AuthLayout title="Two-factor code">
        <form onSubmit={submitCode} className="flex flex-col gap-3">
          <p className="m-0 text-sm text-muted">Enter the 6-digit code from your authenticator app.</p>
          <div>
            <label className="label" htmlFor="mfa-code">
              Authentication code
            </label>
            <input
              id="mfa-code"
              className="field font-mono"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6,8}"
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </div>
          {mfa.error ? <ErrorState error={mfa.error} title="Code not accepted" /> : null}
          <button type="submit" className="btn-primary" disabled={mfa.isPending}>
            {mfa.isPending ? "Checking…" : "Verify"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => setMfaToken(null)}>
            Back
          </button>
        </form>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Sign in">
      <form onSubmit={submitPassword} className="flex flex-col gap-3">
        {state?.registered ? (
          <p role="status" className="m-0 text-sm text-accent">
            Account created. Sign in to continue.
          </p>
        ) : null}
        <div>
          <label className="label" htmlFor="login-email">
            Email
          </label>
          <input
            id="login-email"
            className="field"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="login-password">
            Password
          </label>
          <input
            id="login-password"
            className="field"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {login.error ? <ErrorState error={login.error} title="Sign-in failed" /> : null}
        <button type="submit" className="btn-primary" disabled={login.isPending}>
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>
        <p className="m-0 text-sm text-muted">
          No account?{" "}
          <Link className="text-primary underline" to="/register">
            Create one
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
