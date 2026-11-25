import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";
import { describe, expect, test } from "vitest";
import { routes } from "../routes";

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("AppLayout", () => {
  test("layout shows all nav items", () => {
    renderAt("/");
    const nav = screen.getByRole("navigation", { name: "Main" });
    for (const label of ["Live", "Time Machine", "Arena", "Portfolio"]) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  test("current section is marked for assistive tech", () => {
    renderAt("/arena");
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Arena" })).toHaveAttribute("aria-current", "page");
  });

  test("unknown route shows NotFound", () => {
    renderAt("/does-not-exist");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
