import { create } from "zustand";
import type { AuthState, Client } from "../types";

interface AuthStore extends AuthState {
  setAuth: (token: string, refreshToken: string, client: Client) => void;
  clearAuth: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  accessToken: localStorage.getItem("accessToken"),
  refreshToken: localStorage.getItem("refreshToken"),
  client: null,
  isLoading: false,
  error: null,
  setAuth: (token, refreshToken, client) => {
    localStorage.setItem("accessToken", token);
    localStorage.setItem("refreshToken", refreshToken);
    set({ accessToken: token, refreshToken, client });
  },
  clearAuth: () => {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    set({ accessToken: null, refreshToken: null, client: null });
  },
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));