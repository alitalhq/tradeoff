import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createBrowserRouter } from "react-router";
import { ApiError } from "./api/errors";
import { ToastProvider } from "./components/ui/Toast";
import { routes } from "./routes";
import { ActiveSessionProvider } from "./session/ActiveSession";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Client errors will not fix themselves on retry; network and 5xx errors might.
      retry: (failures, error) => !(error instanceof ApiError && error.status < 500) && failures < 2,
      refetchOnWindowFocus: false,
    },
  },
});
const router = createBrowserRouter(routes);

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ActiveSessionProvider>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </ActiveSessionProvider>
    </QueryClientProvider>
  );
}
