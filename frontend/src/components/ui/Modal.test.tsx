import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { Modal } from "./Modal";

describe("Modal", () => {
  test("shows its title when open and closes on Escape", () => {
    const onClose = vi.fn();
    render(
      <Modal open title="Set limits for period 2" onClose={onClose}>
        <p>body</p>
      </Modal>,
    );
    expect(screen.getByRole("dialog", { name: "Set limits for period 2" })).toBeInTheDocument();
    fireEvent(screen.getByRole("dialog"), new Event("cancel"));
    expect(onClose).toHaveBeenCalled();
  });

  test("renders nothing visible when closed", () => {
    render(
      <Modal open={false} title="Hidden" onClose={() => {}}>
        <p>body</p>
      </Modal>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
