import { useRef, useState, type FormEvent } from "react";
import { useImportRepo, useSources, useUploadSource } from "../../api/projects";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";

const ACCEPT = ".pdf,.docx,.md,.markdown,.json,.yaml,.yml";

function size(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Documents (PDF, DOCX, Markdown, OpenAPI) and read-only Git repositories. */
export function SourcesPanel({ pid }: { pid: string }) {
  const sources = useSources(pid);
  const upload = useUploadSource(pid);
  const repo = useImportRepo(pid);
  const fileRef = useRef<HTMLInputElement>(null);
  const [hasFile, setHasFile] = useState(false);
  const [url, setUrl] = useState("");
  const [ref, setRef] = useState("");

  const onUpload = (e: FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    upload.mutate(file, {
      onSuccess: () => {
        if (fileRef.current) fileRef.current.value = "";
        setHasFile(false);
      },
    });
  };
  const onRepo = (e: FormEvent) => {
    e.preventDefault();
    repo.mutate({ url: url.trim(), ref: ref.trim() || null }, { onSuccess: () => setUrl("") });
  };

  return (
    <section aria-labelledby="sources-heading" className="card">
      <h2 id="sources-heading" className="m-0 mb-3 text-lg font-semibold">
        Sources
      </h2>
      <div className="grid gap-4 md:grid-cols-2">
        <form onSubmit={onUpload} className="flex flex-col gap-2">
          <label className="label" htmlFor="source-file">
            Upload a document
          </label>
          <input
            id="source-file"
            ref={fileRef}
            type="file"
            accept={ACCEPT}
            className="text-sm"
            onChange={(e) => setHasFile(Boolean(e.target.files?.length))}
          />
          <p className="m-0 text-xs text-muted">PDF, DOCX, Markdown or OpenAPI JSON/YAML, up to 50 MB.</p>
          <button type="submit" className="btn-primary self-start" disabled={upload.isPending || !hasFile}>
            {upload.isPending ? "Uploading…" : "Upload"}
          </button>
          {upload.error ? <ErrorState error={upload.error} title="Upload failed" /> : null}
        </form>
        <form onSubmit={onRepo} className="flex flex-col gap-2">
          <div>
            <label className="label" htmlFor="repo-url">
              Git repository (https, read-only)
            </label>
            <input
              id="repo-url"
              className="field"
              type="url"
              placeholder="https://github.com/org/app"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="repo-ref">
              Branch or tag (optional)
            </label>
            <input id="repo-ref" className="field" value={ref} onChange={(e) => setRef(e.target.value)} />
          </div>
          <button type="submit" className="btn-secondary self-start" disabled={repo.isPending}>
            Connect repository
          </button>
          {repo.error ? <ErrorState error={repo.error} title="Could not connect the repository" /> : null}
        </form>
      </div>

      <div className="mt-4">
        {sources.isPending ? (
          <LoadingState label="Loading sources…" />
        ) : sources.error ? (
          <ErrorState error={sources.error} title="Could not load sources" />
        ) : sources.data.items.length === 0 ? (
          <EmptyState title="No sources yet">Upload a PRD or connect a repo so the system can learn the product.</EmptyState>
        ) : (
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">Sources</caption>
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th scope="col" className="p-2">Source</th>
                <th scope="col" className="p-2">Kind</th>
                <th scope="col" className="p-2">Size</th>
                <th scope="col" className="p-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {sources.data.items.map((s) => (
                <tr key={s.id} className="border-b border-border last:border-0">
                  <td className="break-all p-2">{s.filename ?? s.uri}</td>
                  <td className="p-2">{s.kind}</td>
                  <td className="p-2">{size(s.size)}</td>
                  <td className="p-2">
                    {s.status}
                    {s.error ? <span className="block text-xs text-danger">{s.error}</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
