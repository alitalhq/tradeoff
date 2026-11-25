import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-start gap-2 py-12">
      <h1 className="text-lg font-semibold">Page not found</h1>
      <p className="text-sm text-muted">This address doesn't match any screen.</p>
      <Link to="/replay" className="text-sm text-accent underline-offset-4 hover:underline">
        Open the time machine
      </Link>
    </div>
  );
}
