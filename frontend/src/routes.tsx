import { Navigate, type RouteObject } from "react-router";
import { AppLayout } from "./layout/AppLayout";
import { ArenaPage } from "./pages/Arena";
import { LivePage } from "./pages/Live";
import { NotFoundPage } from "./pages/NotFound";
import { PortfolioPage } from "./pages/Portfolio";
import { ReplayPage } from "./pages/Replay";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/replay" replace /> },
      { path: "live", element: <LivePage /> },
      { path: "replay", element: <ReplayPage /> },
      { path: "arena", element: <ArenaPage /> },
      { path: "portfolio", element: <PortfolioPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
