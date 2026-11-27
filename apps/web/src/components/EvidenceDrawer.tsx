/**
 * Evidence for one case of a run (docs/05 §5 run dashboard): screenshots per step, trace / HAR /
 * video / console downloads, failure expected vs actual and the compiled Playwright file.
 * All app-under-test and model text is plain text (it is untrusted data).
 */
import { useEffect, useRef } from "react";
import { downloadUrl } from "../api/client";
import type { CaseRow, EvidenceOut, RunFailure } from "../api/types";
import { VerdictBadge, isVerdict } from "./VerdictBadge";

const KIND_LABEL: Record<string, string> = {
  trace: "Playwright trace",
  video: "Video",
  har: "Network log (HAR)",
  console: "Console log",
  request: "Request log",
};

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function stepLabel(e: EvidenceOut): string {
  return e.step_n === null ? "end of test" : `step ${e.step_n}`;
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="m-0 whitespace-pre-wrap break-words rounded bg-surface-2 p-2 font-mono text-xs">{value}</dd>
    </div>
  );
}

type Props = { pid: string; row: CaseRow; onClose: () => void };

export function EvidenceDrawer({ pid, row, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [onClose]);

  const failure = (row.failure ?? null) as RunFailure | null;
  const screenshots = row.evidence.filter((e) => e.kind === "screenshot");
  const files = row.evidence.filter((e) => e.kind !== "screenshot");
  const headingId = `evidence-${row.case_id}`;

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-labelledby={headingId}
      className="fixed inset-y-0 right-0 z-20 flex w-full max-w-xl flex-col gap-3 overflow-y-auto border-l border-border bg-surface p-4 shadow-lg"
    >
      <div className="flex items-start justify-between gap-2">
        <h2 id={headingId} className="m-0 text-lg font-semibold">
          <span className="block font-mono text-xs text-muted">{row.code}</span>
          {row.title}
        </h2>
        <button ref={closeRef} type="button" className="btn-secondary" onClick={onClose}>
          Close<span className="sr-only"> evidence</span>
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        {isVerdict(row.verdict) ? (
          <VerdictBadge verdict={row.verdict} confidence={(row.level as "high" | "medium" | "low" | null) ?? undefined} />
        ) : (
          <span className="text-muted">No verdict yet</span>
        )}
        {row.rule ? <span className="font-mono text-xs text-muted">rule {row.rule}</span> : null}
        <span className="text-xs text-muted">
          {row.attempts} attempt{row.attempts === 1 ? "" : "s"}
        </span>
      </div>
      {row.verdict === "unable_to_verify" ? (
        <p className="m-0 rounded border border-uv bg-uv-bg p-2 text-sm text-uv">
          Needs a human: this result could not be verified automatically. Check the reason and evidence, then decide.
        </p>
      ) : null}

      <dl className="m-0 flex flex-col gap-2">
        <Field label="Reason" value={row.reason} />
        <Field label="Blocked by" value={row.blocked} />
        {failure ? (
          <>
            <Field
              label="Failure"
              value={[failure.kind, failure.step_n != null ? `step ${failure.step_n}` : null].filter(Boolean).join(" · ")}
            />
            <Field label="Message" value={failure.message} />
            <Field label="Expected (from the cited quote)" value={failure.expected} />
            <Field label="Actual (what the page showed)" value={failure.actual} />
          </>
        ) : null}
      </dl>

      <section aria-labelledby={`${headingId}-shots`}>
        <h3 id={`${headingId}-shots`} className="m-0 mb-2 text-sm font-semibold">
          Screenshots
        </h3>
        {screenshots.length === 0 ? (
          <p className="m-0 text-sm text-muted">No screenshots for this attempt.</p>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {screenshots.map((e) => (
              <li key={e.sha256}>
                <figure className="m-0">
                  <img
                    src={downloadUrl(`/projects/${pid}/evidence/${e.sha256}`)}
                    alt={`Screenshot of ${row.code} at ${stepLabel(e)}`}
                    loading="lazy"
                    className="w-full rounded border border-border"
                  />
                  <figcaption className="text-xs text-muted">{stepLabel(e)}</figcaption>
                </figure>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby={`${headingId}-files`}>
        <h3 id={`${headingId}-files`} className="m-0 mb-2 text-sm font-semibold">
          Downloads
        </h3>
        <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm">
          {files.map((e) => (
            <li key={`${e.kind}-${e.sha256}`}>
              <a className="text-primary underline" href={downloadUrl(`/projects/${pid}/evidence/${e.sha256}`)} download>
                {KIND_LABEL[e.kind] ?? e.kind}
              </a>{" "}
              <span className="text-xs text-muted">
                ({stepLabel(e)}, {size(e.size)})
              </span>
            </li>
          ))}
          <li>
            <a
              className="text-primary underline"
              href={downloadUrl(`/projects/${pid}/cases/${row.case_id}/compiled.py`)}
              download
            >
              Compiled Playwright test (.py)
            </a>
          </li>
        </ul>
      </section>
    </div>
  );
}
