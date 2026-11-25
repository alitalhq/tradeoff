import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <div className="py-12 text-center">
      <h1 className="text-lg font-semibold">Page not found</h1>
      <Link to="/" className="text-sm text-accent">
        Back to start
      </Link>
    </div>
  );
}
