import type { ReactElement } from "react";
import { Link } from "react-router";

/** The answer to a path the route table does not know. */
export function NotFoundView(): ReactElement {
  return (
    <section>
      <h1>Page not found</h1>
      <p>Nothing lives at this address.</p>
      <Link to="/projects">Projects</Link>
    </section>
  );
}
