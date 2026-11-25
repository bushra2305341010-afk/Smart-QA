/** Loading, empty and error states shared by every screen (docs/05 §6 rules 3-5). */
import { useState, type ReactNode } from "react";
import { ApiError } from "../api/client";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-2 py-4">
      <span className="sr-only">{label}</span>
      <div aria-hidden="true" className="h-4 w-1/3 animate-pulse rounded bg-surface-2" />
      <div aria-hidden="true" className="h-4 w-2/3 animate-pulse rounded bg-surface-2" />
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card text-center">
      <p className="m-0 font-semibold">{title}</p>
      {children ? <div className="mt-1 text-sm text-muted">{children}</div> : null}
    </div>
  );
}

/** Says what happened and what to do next; shows the trace id so it can be copied into a bug. */
export function ErrorState({ error, title = "Something went wrong" }: { error: unknown; title?: string }) {
  const [copied, setCopied] = useState(false);
  const api = error instanceof ApiError ? error : null;
  const message = error instanceof Error ? error.message : "Unknown error";
  const copy = async () => {
    if (!api?.traceId) return;
    try {
      await navigator.clipboard.writeText(api.traceId);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div role="alert" className="rounded border border-danger bg-danger-bg p-3 text-sm text-text">
      <p className="m-0 font-semibold">{title}</p>
      <p className="m-0 mt-1">
        {message}
        {api ? <span className="text-muted"> ({api.code})</span> : null}
      </p>
      {api?.traceId ? (
        <p className="m-0 mt-1 text-xs text-muted">
          Trace ID <code className="font-mono">{api.traceId}</code>{" "}
          <button type="button" className="underline" onClick={() => void copy()}>
            {copied ? "Copied" : "Copy"}
          </button>
        </p>
      ) : null}
    </div>
  );
}
