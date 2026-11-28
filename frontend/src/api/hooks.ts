import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Schemas } from "./client";
import { ApiError } from "./errors";

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Turn an openapi-fetch result into data or a thrown ApiError. */
async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call;
  if (!response.ok) throw ApiError.from(response.status, error ?? null);
  return data as T;
}

export const queryKeys = {
  assets: ["assets"] as const,
  session: (id: number) => ["session", id] as const,
  portfolio: (id: number) => ["session", id, "portfolio"] as const,
  orders: (id: number) => ["session", id, "orders"] as const,
  bars: (id: number, assetId: number, timeframe: string) => ["session", id, "bars", assetId, timeframe] as const,
  news: (id: number, assetId: number | null) => ["session", id, "news", assetId] as const,
};

export function useAssets() {
  return useQuery({ queryKey: queryKeys.assets, queryFn: () => unwrap(api.GET("/api/assets")) });
}

export function useSession(sessionId: number | null) {
  return useQuery({
    queryKey: queryKeys.session(sessionId ?? 0),
    queryFn: () => unwrap(api.GET("/api/sessions/{session_id}", { params: { path: { session_id: sessionId! } } })),
    enabled: sessionId !== null,
  });
}

export function usePortfolio(sessionId: number) {
  return useQuery({
    queryKey: queryKeys.portfolio(sessionId),
    queryFn: () =>
      unwrap(api.GET("/api/sessions/{session_id}/portfolio", { params: { path: { session_id: sessionId } } })),
  });
}

export function useOrders(sessionId: number) {
  return useQuery({
    queryKey: queryKeys.orders(sessionId),
    queryFn: () => unwrap(api.GET("/api/sessions/{session_id}/orders", { params: { path: { session_id: sessionId } } })),
  });
}

export function useBars(sessionId: number, assetId: number, timeframe: "1m" | "1h" | "1d" = "1d") {
  return useQuery({
    queryKey: queryKeys.bars(sessionId, assetId, timeframe),
    queryFn: () =>
      unwrap(
        api.GET("/api/sessions/{session_id}/bars", {
          params: { path: { session_id: sessionId }, query: { asset_id: assetId, timeframe } },
        }),
      ),
  });
}

export function useNews(sessionId: number, assetId: number | null = null) {
  return useQuery({
    queryKey: queryKeys.news(sessionId, assetId),
    queryFn: () =>
      unwrap(
        api.GET("/api/sessions/{session_id}/news", {
          params: { path: { session_id: sessionId }, query: assetId === null ? {} : { asset_id: assetId } },
        }),
      ),
  });
}

export function useCreateSession() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["SessionCreate"]) => unwrap(api.POST("/api/sessions", { body })),
    onSuccess: (session) => client.setQueryData(queryKeys.session(session.id), session),
  });
}

export function usePlaceOrder(sessionId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["OrderCreate"]) =>
      unwrap(api.POST("/api/sessions/{session_id}/orders", { params: { path: { session_id: sessionId } }, body })),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.orders(sessionId) }),
  });
}

export function useSetPeriodLimit(sessionId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ periodNo, ...body }: Schemas["PeriodLimitIn"] & { periodNo: number }) =>
      unwrap(
        api.PUT("/api/sessions/{session_id}/periods/{period_no}/limit", {
          params: { path: { session_id: sessionId, period_no: periodNo } },
          body,
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.session(sessionId) }),
  });
}

type ReplayAction = "play" | "pause" | "step";

function useReplayAction(sessionId: number, action: ReplayAction) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () =>
      unwrap(api.POST(`/api/sessions/{session_id}/${action}`, { params: { path: { session_id: sessionId } } })),
    onSuccess: (session) => {
      client.setQueryData(queryKeys.session(sessionId), session);
      // A step can fill orders and apply splits, so everything under the session may be stale.
      if (action === "step") client.invalidateQueries({ queryKey: queryKeys.session(sessionId) });
    },
  });
}

export const usePlay = (sessionId: number) => useReplayAction(sessionId, "play");
export const usePause = (sessionId: number) => useReplayAction(sessionId, "pause");
export const useStep = (sessionId: number) => useReplayAction(sessionId, "step");

export function useSetSpeed(sessionId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (speed: string) =>
      unwrap(api.PUT("/api/sessions/{session_id}/speed", { params: { path: { session_id: sessionId } }, body: { speed } })),
    onSuccess: (session) => client.setQueryData(queryKeys.session(sessionId), session),
  });
}
