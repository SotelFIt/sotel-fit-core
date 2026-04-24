import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { Client } from "../types";
import api from "../services/api";

export default function Dashboard() {
  const [client, setClient] = useState<Client | null>(null);
  const navigate = useNavigate();
  const { accessToken, clearAuth } = useAuthStore();

  useEffect(() => {
    if (!accessToken) {
      navigate("/login");
      return;
    }

    const fetchClient = async () => {
      try {
        const response = await api.get("/auth/me");
        setClient(response.data);
      } catch (error) {
        console.error("Failed to fetch client:", error);
        clearAuth();
        navigate("/login");
      }
    };

    fetchClient();
  }, [accessToken, navigate, clearAuth]);

  const handleLogout = () => {
    clearAuth();
    navigate("/login");
  };

  if (!client) return <div className="p-8">Carregando...</div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-md p-4">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold">Sotel Fit</h1>
          <button onClick={handleLogout} className="bg-red-600 text-white p-2 rounded">
            Logout
          </button>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto p-8">
        <h2 className="text-3xl font-bold mb-6">Bem-vindo, {client.name}</h2>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold">Treino Hoje</h3>
            <p className="text-gray-600">Nenhum treino agendado</p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold">Próximo Check-in</h3>
            <p className="text-gray-600">Em 3 dias</p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold">Objetivo</h3>
            <p className="text-gray-600">{client.objective}</p>
          </div>
        </div>
      </main>
    </div>
  );
}