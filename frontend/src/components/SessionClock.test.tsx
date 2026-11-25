import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { SessionClock } from "./SessionClock";

const periods = [
  { period_no: 1, starts_at: "2019-01-02T21:00:00Z", ends_at: "2019-01-17T21:00:00Z" },
  { period_no: 2, starts_at: "2019-01-17T21:00:00Z", ends_at: "2019-02-01T21:00:00Z" },
];

describe("SessionClock", () => {
  test("shows the session date and how far the replay has progressed", () => {
    render(
      <SessionClock
        simTime="2019-01-17T21:00:00Z"
        startAt="2019-01-02T21:00:00Z"
        endAt="2019-02-01T21:00:00Z"
        status="running"
        periods={periods}
      />,
    );
    expect(screen.getByText("Jan 17, 2019")).toBeInTheDocument();
    const progress = screen.getByRole("progressbar", { name: "Replay progress" });
    expect(progress).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("Period 2 of 2")).toBeInTheDocument();
  });

  test("live sessions have no progress rail", () => {
    render(<SessionClock simTime="2026-11-25T15:00:00Z" startAt="2026-11-25T14:30:00Z" endAt={null} status="running" />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  test("shows an invitation when no session is open", () => {
    render(<SessionClock />);
    expect(screen.getByText("No session open")).toBeInTheDocument();
  });
});
