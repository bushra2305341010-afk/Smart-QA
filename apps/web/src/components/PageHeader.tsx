import type { ReactNode } from "react";

type Props = { title: string; description?: ReactNode; actions?: ReactNode };

export function PageHeader({ title, description, actions }: Props) {
  return (
    <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="m-0 text-2xl font-bold">{title}</h1>
        {description ? <p className="m-0 mt-1 text-sm text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}
