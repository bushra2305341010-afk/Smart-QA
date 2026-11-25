import { Link } from "react-router-dom";
import { PageHeader } from "../components/PageHeader";

export function NotFoundPage() {
  return (
    <section>
      <PageHeader title="Page not found" description="This address does not match any screen." />
      <Link className="text-primary underline" to="/projects">
        Go to your projects
      </Link>
    </section>
  );
}
