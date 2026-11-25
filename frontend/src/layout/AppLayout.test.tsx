import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";
import { describe, expect, test } from "vitest";
import { routes } from "../routes";

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<RouterProvider router={router} />);
}

describe("AppLayout", () => {
  test("layout shows all nav items", () => {
    renderAt("/");
    for (const label of ["Live", "Time Machine", "Arena", "Portfolio"]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  test("unknown route shows NotFound", () => {
    renderAt("/does-not-exist");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
