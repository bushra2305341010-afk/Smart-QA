import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useRegister } from "../../api/auth";
import { ErrorState } from "../../components/States";
import { AuthLayout } from "./AuthLayout";

export function RegisterPage() {
  const navigate = useNavigate();
  const register = useRegister();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    register.mutate(
      { email, password },
      { onSuccess: () => navigate("/login", { state: { registered: true } }) },
    );
  };

  return (
    <AuthLayout title="Create account">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <div>
          <label className="label" htmlFor="reg-email">
            Email
          </label>
          <input
            id="reg-email"
            className="field"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="reg-password">
            Password
          </label>
          <input
            id="reg-password"
            className="field"
            type="password"
            autoComplete="new-password"
            aria-describedby="reg-password-hint"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p id="reg-password-hint" className="m-0 mt-1 text-xs text-muted">
            Use a long passphrase. Known breached passwords are refused.
          </p>
        </div>
        {register.error ? <ErrorState error={register.error} title="Could not create the account" /> : null}
        <button type="submit" className="btn-primary" disabled={register.isPending}>
          {register.isPending ? "Creating…" : "Create account"}
        </button>
        <p className="m-0 text-sm text-muted">
          Already registered?{" "}
          <Link className="text-primary underline" to="/login">
            Sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
