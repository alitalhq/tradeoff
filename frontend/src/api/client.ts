import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type Bar = Schemas["Bar"];
export type NewsItem = Schemas["NewsItem"];

export const DEV_USER_KEY = "tradeoff.devUserId";

export function devUserId(): string | null {
  try {
    return localStorage.getItem(DEV_USER_KEY);
  } catch {
    return null;
  }
}

// Temporary until the auth plan lands: the backend trusts X-User-Id only in dev/test.
const devAuth: Middleware = {
  onRequest({ request }) {
    const userId = import.meta.env.DEV ? devUserId() : null;
    if (userId) request.headers.set("X-User-Id", userId);
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: "/" });
api.use(devAuth);
