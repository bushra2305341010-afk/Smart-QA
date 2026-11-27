import { useState, type FormEvent } from "react";
import { useCreateEnvironment, useEnvironments } from "../../api/projects";
import type { EnvironmentIn } from "../../api/types";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";

const KINDS: EnvironmentIn["kind"][] = ["local", "staging", "public", "production"];

/** Where tests run. The base URL's host is added to the allowed hosts; production needs Owner. */
export function EnvironmentsPanel({ pid }: { pid: string }) {
  const envs = useEnvironments(pid);
  const create = useCreateEnvironment(pid);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<EnvironmentIn["kind"]>("staging");
  const [baseUrl, setBaseUrl] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      { name: name.trim(), kind, base_url: baseUrl.trim() },
      {
        onSuccess: () => {
          setName("");
          setBaseUrl("");
        },
      },
    );
  };

  return (
    <section aria-labelledby="env-heading" className="card">
      <h2 id="env-heading" className="m-0 mb-3 text-lg font-semibold">
        Environments
      </h2>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <div>
          <label className="label" htmlFor="env-name">
            Name
          </label>
          <input id="env-name" className="field" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="env-kind">
            Kind
          </label>
          <select
            id="env-kind"
            className="field"
            value={kind}
            onChange={(e) => setKind(e.target.value as EnvironmentIn["kind"])}
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-64 flex-1">
          <label className="label" htmlFor="env-url">
            Base URL
          </label>
          <input
            id="env-url"
            className="field"
            type="url"
            placeholder="https://staging.example.com"
            required
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary" disabled={create.isPending}>
          Add environment
        </button>
      </form>
      {kind === "production" ? (
        <p className="m-0 mt-2 text-xs text-flaky">Production environments need the Owner role and run safe actions only.</p>
      ) : null}
      {create.error ? (
        <div className="mt-2">
          <ErrorState error={create.error} title="Could not add the environment" />
        </div>
      ) : null}
      <div className="mt-4">
        {envs.isPending ? (
          <LoadingState label="Loading environments…" />
        ) : envs.error ? (
          <ErrorState error={envs.error} title="Could not load environments" />
        ) : envs.data.length === 0 ? (
          <EmptyState title="No environments yet">Add the staging URL the runner should test.</EmptyState>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {envs.data.map((env) => (
              <li key={env.id} className="rounded border border-border p-2 text-sm">
                <span className="font-semibold">{env.name}</span> <span className="text-muted">({env.kind})</span>
                <span className="block break-all">{env.base_url}</span>
                <span className="block text-xs text-muted">Allowed hosts: {env.allowed_hosts.join(", ") || "—"}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
