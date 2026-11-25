import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

const STORAGE_KEY = "tradeoff.activeSessionId";

interface ActiveSessionValue {
  sessionId: number | null;
  setSessionId: (id: number | null) => void;
}

const ActiveSessionContext = createContext<ActiveSessionValue>({ sessionId: null, setSessionId: () => {} });

function readStored(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? Number(raw) : null;
  } catch {
    return null;
  }
}

/** The session the header clock follows; remembered per browser. */
export function ActiveSessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setState] = useState<number | null>(readStored);
  const setSessionId = useCallback((id: number | null) => {
    setState(id);
    try {
      if (id === null) localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, String(id));
    } catch {
      // Storage may be unavailable (private mode); the choice then lasts for this tab only.
    }
  }, []);
  return <ActiveSessionContext.Provider value={{ sessionId, setSessionId }}>{children}</ActiveSessionContext.Provider>;
}

export function useActiveSession(): ActiveSessionValue {
  return useContext(ActiveSessionContext);
}
