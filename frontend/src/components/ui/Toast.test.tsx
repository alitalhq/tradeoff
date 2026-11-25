import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { ToastProvider, useToast } from "./Toast";

function Trigger() {
  const toast = useToast();
  return <button onClick={() => toast.show("Order placed", "success")}>go</button>;
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("Toast", () => {
  test("announces the message and dismisses itself", () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    act(() => screen.getByText("go").click());
    expect(screen.getByRole("status")).toHaveTextContent("Order placed");
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByRole("status")).not.toHaveTextContent("Order placed");
  });
});
