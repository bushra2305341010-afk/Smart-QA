import type { CaseCitation, CaseOut } from "../../api/types";
import { CitationQuote } from "../../components/CitationQuote";
import { StatusBadge } from "../../components/StatusBadge";
import { VerdictBadge } from "../../components/VerdictBadge";

export function isVerified(c: CaseOut): boolean {
  return (c.citation as CaseCitation | null)?.status === "verified";
}

type Props = {
  testCase: CaseOut;
  busy: boolean;
  onDecide: (decision: "approved" | "rejected") => void;
};

/** A case with its expected result and the quote that proves it. Unverified cases cannot pass Gate 3. */
export function CaseDetail({ testCase: c, busy, onDecide }: Props) {
  const citation = c.citation as CaseCitation | null;
  const verified = isVerified(c);
  const reviewable = c.review_status === "pending" || c.review_status === "edited";
  const data = Object.entries(c.data);
  return (
    <article aria-labelledby="case-title" className="card flex flex-col gap-3">
      <header className="flex flex-col gap-1">
        <p className="m-0 font-mono text-xs text-muted">
          {c.code} · {c.technique.replace(/_/g, " ")} · {c.role} · {c.priority}
        </p>
        <h2 id="case-title" className="m-0 text-lg font-semibold">
          {c.title}
        </h2>
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={c.review_status} />
          {!verified ? <VerdictBadge verdict="unable_to_verify" /> : null}
        </div>
      </header>
      {c.preconditions.length > 0 ? (
        <section>
          <h3 className="m-0 text-sm font-semibold">Preconditions</h3>
          <ul className="m-0 pl-5 text-sm">
            {c.preconditions.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <section>
        <h3 className="m-0 text-sm font-semibold">Steps</h3>
        <ol className="m-0 pl-5 text-sm">
          {c.steps.map((s) => (
            <li key={s.n}>{s.action}</li>
          ))}
        </ol>
      </section>
      {data.length > 0 ? (
        <section>
          <h3 className="m-0 text-sm font-semibold">Test data</h3>
          <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-3 text-sm">
            {data.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="font-mono text-muted">{k}</dt>
                <dd className="m-0 break-all font-mono">{typeof v === "string" ? v : JSON.stringify(v)}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
      <section className="flex flex-col gap-1">
        <h3 className="m-0 text-sm font-semibold">Expected result</h3>
        <p className="m-0 text-sm">{c.expected_text}</p>
        <CitationQuote quote={citation?.quote} status={citation?.status ?? "unable_to_verify"} reason={citation?.reason} />
      </section>
      {reviewable ? (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="btn-primary"
            aria-keyshortcuts="A"
            disabled={busy || !verified}
            aria-describedby={verified ? undefined : "uv-note"}
            onClick={() => onDecide("approved")}
          >
            Approve case
          </button>
          <button
            type="button"
            className="btn-danger"
            aria-keyshortcuts="R"
            disabled={busy}
            onClick={() => onDecide("rejected")}
          >
            Reject case
          </button>
          {!verified ? (
            <p id="uv-note" className="m-0 text-xs text-uv">
              Unable to Verify: the quote was not found in the source, so this case cannot be approved. Reject it.
            </p>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
