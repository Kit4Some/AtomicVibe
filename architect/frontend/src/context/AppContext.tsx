import {
  createContext,
  useContext,
  useReducer,
  type Dispatch,
  type ReactNode,
} from "react";
import type { Tier } from "../api/types";

interface AppState {
  planId: string | null;
  jobId: string | null;
  apiKeyConfigured: boolean | null; // null = loading
  tier: Tier;
}

type Action =
  | { type: "SET_PLAN_ID"; payload: string | null }
  | { type: "SET_JOB_ID"; payload: string | null }
  | { type: "SET_API_KEY_CONFIGURED"; payload: boolean }
  | { type: "SET_TIER"; payload: Tier };

const initialState: AppState = {
  planId: null,
  jobId: null,
  apiKeyConfigured: null,
  tier: "mid",
};

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "SET_PLAN_ID":
      return { ...state, planId: action.payload };
    case "SET_JOB_ID":
      return { ...state, jobId: action.payload };
    case "SET_API_KEY_CONFIGURED":
      return { ...state, apiKeyConfigured: action.payload };
    case "SET_TIER":
      return { ...state, tier: action.payload };
  }
}

const AppContext = createContext<AppState>(initialState);
const DispatchContext = createContext<Dispatch<Action>>(() => {});

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <AppContext.Provider value={state}>
      <DispatchContext.Provider value={dispatch}>
        {children}
      </DispatchContext.Provider>
    </AppContext.Provider>
  );
}

export function useAppState() {
  return useContext(AppContext);
}

export function useAppDispatch() {
  return useContext(DispatchContext);
}
