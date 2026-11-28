import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "./client";
import { ApiError } from "./errors";
import { queryKeys, useSetSpeed, useStep } from "./hooks";

const session = { id: 7, status: "paused", sim_time: "2019-01-03T21:00:00Z" };

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}

function reply(status: number, body: unknown) {
  const ok = status < 400;
  return { data: ok ? body : undefined, error: ok ? undefined : body, response: new Response(null, { status }) };
}

afterEach(() => vi.restoreAllMocks());

test("step posts to the session and stores the returned session", async () => {
  const post = vi.spyOn(api, "POST").mockResolvedValue(reply(200, session) as never);
  const { client, wrapper } = setup();
  const { result } = renderHook(() => useStep(7), { wrapper });
  await act(() => result.current.mutateAsync());
  expect(post).toHaveBeenCalledWith("/api/sessions/{session_id}/step", { params: { path: { session_id: 7 } } });
  expect(client.getQueryData(queryKeys.session(7))).toEqual(session);
});

test("a blocked step surfaces the reason", async () => {
  vi.spyOn(api, "POST").mockResolvedValue(reply(409, { detail: { reason: "limits_required" } }) as never);
  const { wrapper } = setup();
  const { result } = renderHook(() => useStep(7), { wrapper });
  act(() => result.current.mutate());
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect((result.current.error as ApiError).reason).toBe("limits_required");
});

test("speed is sent as a string", async () => {
  const put = vi.spyOn(api, "PUT").mockResolvedValue(reply(200, { ...session, speed: "4.00" }) as never);
  const { wrapper } = setup();
  const { result } = renderHook(() => useSetSpeed(7), { wrapper });
  await act(() => result.current.mutateAsync("4"));
  expect(put).toHaveBeenCalledWith("/api/sessions/{session_id}/speed", {
    params: { path: { session_id: 7 } },
    body: { speed: "4" },
  });
});
