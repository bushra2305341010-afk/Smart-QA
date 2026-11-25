import type { ReactNode } from "react";

export function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4 text-text">
      <section className="card w-full max-w-sm">
        <p className="m-0 text-sm font-semibold text-primary">Smart Autonomous QA</p>
        <h1 className="m-0 mb-4 mt-1 text-2xl font-bold">{title}</h1>
        {children}
      </section>
    </main>
  );
}
