import { useState, useEffect } from "react";
import type { Client } from "../types";
import api from "../services/api";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

export default function Dashboard() {
  const [client, setClient] = useState<Client | null>(null);
  const navigate = useNavigate();
  const { accessToken, clearAuth } = useAuthStore();

  useEffect(() => {
    if (!accessToken) { navigate("/login"); return; }
    api.get("/auth/me").then(r => setClient(r.data)).catch(() => { clearAuth(); navigate("/login"); });
  }, []);

  if (!client) return <div>Carregando...</div>;

  return <div>{client.name}</div>;
}