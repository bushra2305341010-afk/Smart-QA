/**
 * The source quote behind an AI claim (pillar P1). Quotes are untrusted document text, so
 * they are rendered as plain text only. An unverified quote is labelled, never presented as fact.
 */
type Props = {
  quote: string | null | undefined;
  status: string;
  file?: string | null;
  page?: number | null;
  line?: number | null;
  reason?: string | null;
};

function location(file?: string | null, page?: number | null, line?: number | null): string {
  const parts = [file ?? "source", page != null ? `p. ${page}` : null, line != null ? `line ${line}` : null];
  return parts.filter(Boolean).join(" · ");
}

export function CitationQuote({ quote, status, file, page, line, reason }: Props) {
  const verified = status === "verified";
  return (
    <figure className="m-0 rounded border border-border bg-surface p-2">
      <figcaption className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span
          className={`rounded-full px-2 py-0.5 font-semibold ${
            verified ? "border border-accent text-accent" : "bg-uv-bg text-uv"
          }`}
        >
          <span aria-hidden="true">{verified ? "✓ " : "? "}</span>
          {verified ? "AI · cited" : "AI · unverified"}
        </span>
        <span>{location(file, page, line)}</span>
      </figcaption>
      {quote ? (
        <blockquote className="m-0 whitespace-pre-wrap rounded bg-quote px-2 py-1 text-sm text-text">
          {quote}
        </blockquote>
      ) : (
        <p className="m-0 text-sm text-muted">No source quote.</p>
      )}
      {!verified && reason ? <p className="m-0 mt-1 text-xs text-muted">Why unverified: {reason}</p> : null}
    </figure>
  );
}
