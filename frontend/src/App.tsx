import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";

const API = "http://localhost:8000";

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(API + "/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (data.access_token) {
        localStorage.setItem("accessToken", data.access_token);
        localStorage.setItem("client", JSON.stringify(data.client));
        navigate("/dashboard");
      } else {
        alert("Email nao encontrado");
      }
    } catch {
      alert("Erro ao conectar com servidor");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f4f8" }}>
      <div style={{ background: "white", padding: "40px", borderRadius: "12px", boxShadow: "0 4px 20px rgba(0,0,0,0.1)", width: "380px" }}>
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <h1 style={{ fontSize: "28px", fontWeight: "700", color: "#1e40af" }}>Sotel Fit</h1>
          <p style={{ color: "#6b7280", marginTop: "8px" }}>Entre na sua conta</p>
        </div>
        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", marginBottom: "6px", fontWeight: "500", color: "#374151" }}>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="seu@email.com" style={{ width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: "24px" }}>
            <label style={{ display: "block", marginBottom: "6px", fontWeight: "500", color: "#374151" }}>Senha</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" style={{ width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", boxSizing: "border-box" }} />
          </div>
          <button type="submit" disabled={loading} style={{ width: "100%", padding: "12px", background: "#2563eb", color: "white", border: "none", borderRadius: "8px", fontSize: "16px", fontWeight: "600", cursor: "pointer" }}>
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}

function Dashboard() {
  const navigate = useNavigate();
  const token = localStorage.getItem("accessToken");
  const clientRaw = localStorage.getItem("client");
  const client = clientRaw ? JSON.parse(clientRaw) : null;

  if (!token) return <Navigate to="/login" />;

  const cards = [
    { title: "Treino de Hoje", value: "Nenhum agendado", icon: "💪" },
    { title: "Proximo Check-in", value: "Em 3 dias", icon: "📋" },
    { title: "Objetivo", value: client?.objective || "-", icon: "🎯" },
    { title: "Status", value: client?.is_active ? "Ativo" : "Inativo", icon: "✅" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: "#f0f4f8", fontFamily: "Arial" }}>
      <nav style={{ background: "#2563eb", color: "white", padding: "16px 32px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ fontSize: "22px", fontWeight: "700" }}>Sotel Fit</h1>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <span style={{ fontSize: "14px" }}>{client?.name || client?.email}</span>
          <button onClick={() => { localStorage.clear(); navigate("/login"); }} style={{ background: "white", color: "#2563eb", border: "none", padding: "8px 16px", borderRadius: "6px", cursor: "pointer", fontWeight: "600" }}>Sair</button>
        </div>
      </nav>

      <main style={{ maxWidth: "1100px", margin: "0 auto", padding: "32px 16px" }}>
        <h2 style={{ fontSize: "24px", fontWeight: "700", marginBottom: "8px" }}>Ola, {client?.name?.split(" ")[0]}! 👋</h2>
        <p style={{ color: "#6b7280", marginBottom: "32px" }}>Aqui esta um resumo do seu progresso</p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px", marginBottom: "32px" }}>
          {cards.map((card, i) => (
            <div key={i} style={{ background: "white", borderRadius: "12px", padding: "20px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
              <div style={{ fontSize: "32px", marginBottom: "12px" }}>{card.icon}</div>
              <p style={{ color: "#6b7280", fontSize: "12px", marginBottom: "4px" }}>{card.title}</p>
              <p style={{ fontWeight: "700", fontSize: "16px" }}>{card.value}</p>
            </div>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "16px" }}>
          <div style={{ background: "white", borderRadius: "12px", padding: "24px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
            <h3 style={{ fontWeight: "700", marginBottom: "16px" }}>📊 Seu Plano de Treino</h3>
            <p style={{ color: "#6b7280" }}>Nenhum treino configurado ainda. Aguarde seu treinador montar seu plano.</p>
          </div>
          <div style={{ background: "white", borderRadius: "12px", padding: "24px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
            <h3 style={{ fontWeight: "700", marginBottom: "16px" }}>🥗 Alimentacao</h3>
            <p style={{ color: "#6b7280" }}>Plano alimentar em breve.</p>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/" element={<Navigate to="/login" />} />
      </Routes>
    </BrowserRouter>
  );
}