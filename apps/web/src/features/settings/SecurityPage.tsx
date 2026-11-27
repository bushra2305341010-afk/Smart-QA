import { useState, type FormEvent } from "react";
import { useTotpEnable, useTotpSetup } from "../../api/auth";
import { PageHeader } from "../../components/PageHeader";
import { ErrorState } from "../../components/States";

/** Turn on two-factor sign-in: get a secret (shown once), then confirm one code. */
export function SecurityPage() {
  const setup = useTotpSetup();
  const enable = useTotpEnable();
  const [code, setCode] = useState("");

  const confirm = (e: FormEvent) => {
    e.preventDefault();
    enable.mutate(code.trim());
  };

  return (
    <section className="max-w-xl">
      <PageHeader title="Security" description="Two-factor sign-in with an authenticator app (TOTP)." />
      {enable.isSuccess ? (
        <p role="status" className="card m-0 text-accent">
          Two-factor sign-in is on. You will be asked for a code at each sign-in.
        </p>
      ) : setup.data ? (
        <form onSubmit={confirm} className="card flex flex-col gap-3">
          <p className="m-0 text-sm">
            Add this secret to your authenticator app. It is shown only once.
          </p>
          <p className="m-0">
            <span className="label">Secret</span>
            <code className="block break-all rounded bg-surface-2 p-2 font-mono text-sm">{setup.data.secret}</code>
          </p>
          <p className="m-0">
            <span className="label">Setup URI</span>
            <code className="block break-all rounded bg-surface-2 p-2 font-mono text-xs">{setup.data.otpauth_uri}</code>
          </p>
          <div>
            <label className="label" htmlFor="totp-code">
              Code from the app
            </label>
            <input
              id="totp-code"
              className="field w-40 font-mono"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </div>
          {enable.error ? <ErrorState error={enable.error} title="Code not accepted" /> : null}
          <button type="submit" className="btn-primary self-start" disabled={enable.isPending}>
            Turn on two-factor
          </button>
        </form>
      ) : (
        <div className="card flex flex-col items-start gap-3">
          <p className="m-0 text-sm text-muted">Two-factor protects your account if your password leaks.</p>
          {setup.error ? <ErrorState error={setup.error} title="Could not start setup" /> : null}
          <button type="button" className="btn-primary" disabled={setup.isPending} onClick={() => setup.mutate()}>
            Set up two-factor
          </button>
        </div>
      )}
    </section>
  );
}
