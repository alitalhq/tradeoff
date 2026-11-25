import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { DEV_USER_KEY } from "../api/client";
import { DevUserSwitcher } from "./DevUserSwitcher";

describe("DevUserSwitcher", () => {
  test("stores the chosen development user id", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <DevUserSwitcher />
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText("Dev user id"), { target: { value: "3" } });
    fireEvent.submit(screen.getByRole("form", { name: "Switch dev user" }));
    expect(localStorage.getItem(DEV_USER_KEY)).toBe("3");
  });
});
