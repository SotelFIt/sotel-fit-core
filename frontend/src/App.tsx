import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ─── TIPOS ───────────────────────────────────────────────────────────────────

interface Lead {
  phone: string;
  name: string | null;
  goal: string | null;
  routine: string | null;
  status: string;
  step: string;
  onboarding_link_sent: boolean;
  created_at: string;
}

// ─── NAVBAR CLIENTE ───────────────────────────────────────────────────────────

function Navbar({ client, onLogout }: any) {
  const navigate = useNavigate();
  return (
    <nav style={{ background: "#2563eb", color: "white", padding: "16px 32px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <h1 onClick={() => navigate("/dashboard")} style={{ fontSize: "22px", fontWeight: "700", cursor: "pointer" }}>Sotel Fit</h1>
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <span onClick={() => navigate("/checkin")} style={{ fontSize: "14px", cursor: "pointer", opacity: 0.8 }}>Check-in</span>
        <span style={{ fontSize: "14px" }}>{client?.name}</span>
        <button onClick={onLogout} style={{ background: "white", color: "#2563eb", border: "none", padding: "8px 16px", borderRadius: "6px", cursor: "pointer", fontWeight: "600" }}>Sair</button>
      </div>
    </nav>
  );
}

// ─── ONBOARDING ───────────────────────────────────────────────────────────────

function Onboarding() {
  const [step, setStep] = useState<"welcome" | "form" | "done">("welcome");
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    nome: "", email: "", telefone: "", idade: "", peso: "", altura: "",
    objetivo: "", nivel_treino: "", dias_treino: "", horario_treino: "",
    lesoes: "", alimentacao_atual: "", maior_dificuldade: "", meta_principal: "", observacoes: ""
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await fetch(API + "/onboarding/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setStep("done");
    } catch {
      alert("Erro ao enviar. Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  const input = (label: string, name: string, type = "text", placeholder = "") => (
    <div style={{ marginBottom: "16px" }}>
      <label style={{ display: "block", fontWeight: "600", marginBottom: "6px", color: "#374151", fontSize: "14px" }}>{label}</label>
      <input type={type} name={name} placeholder={placeholder} value={(form as any)[name]} onChange={handleChange} required
        style={{ width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", boxSizing: "border-box" }} />
    </div>
  );

  const textarea = (label: string, name: string, placeholder = "") => (
    <div style={{ marginBottom: "16px" }}>
      <label style={{ display: "block", fontWeight: "600", marginBottom: "6px", color: "#374151", fontSize: "14px" }}>{label}</label>
      <textarea name={name} placeholder={placeholder} value={(form as any)[name]} onChange={handleChange}
        style={{ width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", boxSizing: "border-box", height: "80px", resize: "vertical" }} />
    </div>
  );

  const select = (label: string, name: string, options: string[]) => (
    <div style={{ marginBottom: "16px" }}>
      <label style={{ display: "block", fontWeight: "600", marginBottom: "6px", color: "#374151", fontSize: "14px" }}>{label}</label>
      <select name={name} value={(form as any)[name]} onChange={handleChange} required
        style={{ width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", boxSizing: "border-box" }}>
        <option value="">Selecione...</option>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );

  if (step === "welcome") return (
    <div style={{ minHeight: "100vh", background: "#0f172a", display: "flex", alignItems: "center", justifyContent: "center", padding: "20px", fontFamily: "Arial" }}>
      <div style={{ maxWidth: "480px", width: "100%", textAlign: "center" }}>
        <div style={{ fontSize: "48px", marginBottom: "16px" }}>💪</div>
        <h1 style={{ fontSize: "28px", fontWeight: "700", color: "white", marginBottom: "12px" }}>Bem-vindo ao Sotel Fit Core</h1>
        <p style={{ color: "#94a3b8", fontSize: "16px", marginBottom: "32px", lineHeight: "1.6" }}>
          Antes de liberar seu plano personalizado, precisamos conhecer sua rotina, objetivo e ponto de partida.
        </p>
        <button onClick={() => setStep("form")} style={{ width: "100%", padding: "16px", background: "#2563eb", color: "white", border: "none", borderRadius: "10px", fontSize: "18px", fontWeight: "700", cursor: "pointer" }}>
          Começar meu cadastro →
        </button>
      </div>
    </div>
  );

  if (step === "done") return (
    <div style={{ minHeight: "100vh", background: "#0f172a", display: "flex", alignItems: "center", justifyContent: "center", padding: "20px", fontFamily: "Arial" }}>
      <div style={{ maxWidth: "480px", width: "100%", textAlign: "center" }}>
        <div style={{ fontSize: "64px", marginBottom: "16px" }}>✅</div>
        <h2 style={{ fontSize: "26px", fontWeight: "700", color: "white", marginBottom: "12px" }}>Cadastro recebido!</h2>
        <p style={{ color: "#94a3b8", fontSize: "16px", lineHeight: "1.6" }}>
          Agora o time Sotel vai montar seu plano personalizado.<br />
          Assim que estiver pronto, você será avisado pelo WhatsApp.
        </p>
      </div>
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: "#f0f4f8", fontFamily: "Arial" }}>
      <div style={{ background: "#0f172a", padding: "20px 32px" }}>
        <h1 style={{ color: "white", fontSize: "20px", fontWeight: "700" }}>Sotel Fit Core</h1>
        <p style={{ color: "#94a3b8", fontSize: "13px", marginTop: "4px" }}>Complete seu cadastro para liberar seu plano</p>
      </div>
      <main style={{ maxWidth: "600px", margin: "0 auto", padding: "32px 16px" }}>
        <form onSubmit={handleSubmit} style={{ background: "white", borderRadius: "12px", padding: "32px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <h2 style={{ fontSize: "20px", fontWeight: "700", marginBottom: "24px", color: "#1e40af" }}>📋 Dados Pessoais</h2>
          {input("Nome completo", "nome", "text", "Seu nome")}
          {input("Email", "email", "email", "seu@email.com")}
          {input("WhatsApp", "telefone", "text", "+55 17 99999-9999")}
          {input("Idade", "idade", "number", "Ex: 28")}
          {input("Peso atual (kg)", "peso", "number", "Ex: 75")}
          {input("Altura (cm)", "altura", "number", "Ex: 175")}
          <h2 style={{ fontSize: "20px", fontWeight: "700", margin: "24px 0 16px", color: "#1e40af" }}>🎯 Objetivo e Rotina</h2>
          {select("Objetivo principal", "objetivo", ["Emagrecimento", "Ganho de massa", "Condicionamento", "Melhorar saúde e rotina"])}
          {select("Nível de treino", "nivel_treino", ["Iniciante", "Intermediário", "Avançado"])}
          {select("Quantos dias pode treinar por semana?", "dias_treino", ["1 dia", "2 dias", "3 dias", "4 dias", "5 dias", "6 dias"])}
          {select("Horário que costuma treinar", "horario_treino", ["Manhã", "Tarde", "Noite", "Variado"])}
          <h2 style={{ fontSize: "20px", fontWeight: "700", margin: "24px 0 16px", color: "#1e40af" }}>🩺 Saúde e Alimentação</h2>
          {textarea("Lesões ou restrições físicas", "lesoes", "Ex: Dor no joelho, hérnia... ou Nenhuma")}
          {textarea("Como está sua alimentação atual?", "alimentacao_atual", "Descreva sua rotina alimentar")}
          {textarea("Qual sua maior dificuldade hoje?", "maior_dificuldade", "Ex: Falta de tempo, fome, motivação...")}
          {textarea("Qual sua meta principal?", "meta_principal", "O que você quer conquistar?")}
          {textarea("Observações adicionais", "observacoes", "Alguma informação extra?")}
          <button type="submit" disabled={loading} style={{ width: "100%", padding: "14px", background: "#2563eb", color: "white", border: "none", borderRadius: "8px", fontSize: "16px", fontWeight: "700", cursor: "pointer", marginTop: "8px" }}>
            {loading ? "Enviando..." : "Enviar meu cadastro ✓"}
          </button>
        </form>
      </main>
    </div>
  );
}

// ─── LOGIN CLIENTE ────────────────────────────────────────────────────────────

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
        alert("Email ou senha incorretos");
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
            <label style={{ display: "block", marginBottom: "6px", fontWeight: "500", color: "#374151" }}>E-mail</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="seu@email.com"
              style={{ width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: "24px" }}>
            <label style={{ display: "block", marginBottom: "6px", fontWeight: "500", color: "#374151" }}>Senha</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••"
              style={{ width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", boxSizing: "border-box" }} />
          </div>
          <button type="submit" disabled={loading} style={{ width: "100%", padding: "12px", background: "#2563eb", color: "white", border: "none", borderRadius: "8px", fontSize: "16px", fontWeight: "600", cursor: "pointer" }}>
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}

// ─── DASHBOARD CLIENTE ────────────────────────────────────────────────────────

function Dashboard() {
  const navigate = useNavigate();
  const token = localStorage.getItem("accessToken");
  const clientRaw = localStorage.getItem("client");
  const client = clientRaw ? JSON.parse(clientRaw) : null;

  if (!token) return <Navigate to="/login" />;

  const logout = () => { localStorage.clear(); navigate("/login"); };

  const cards = [
    { title: "Treino de Hoje", value: "Nenhum agendado", icon: "💪" },
    { title: "Proximo Check-in", value: "Em 3 dias", icon: "📋" },
    { title: "Objetivo", value: client?.objective || "-", icon: "🎯" },
    { title: "Status", value: client?.is_active ? "Ativo" : "Inativo", icon: "✅" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: "#f0f4f8", fontFamily: "Arial" }}>
      <Navbar client={client} onLogout={logout} />
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
          <div style={{ background: "white", borderRadius: "12px", padding: "24px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)", cursor: "pointer" }} onClick={() => navigate("/checkin")}>
            <h3 style={{ fontWeight: "700", marginBottom: "16px" }}>📋 Check-in Semanal</h3>
            <p style={{ color: "#6b7280", marginBottom: "12px" }}>Responda como foi sua semana.</p>
            <button style={{ background: "#2563eb", color: "white", border: "none", padding: "8px 16px", borderRadius: "6px", cursor: "pointer" }}>Fazer Check-in</button>
          </div>
        </div>
      </main>
    </div>
  );
}

// ─── CHECKIN ──────────────────────────────────────────────────────────────────

function Checkin() {
  const navigate = useNavigate();
  const token = localStorage.getItem("accessToken");
  const clientRaw = localStorage.getItem("client");
  const client = clientRaw ? JSON.parse(clientRaw) : null;
  const [form, setForm] = useState({ treinou: "", seguiu_dieta: "", peso: "", dificuldade: "", observacoes: "" });
  const [enviado, setEnviado] = useState(false);

  if (!token) return <Navigate to="/login" />;

  const logout = () => { localStorage.clear(); navigate("/login"); };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setEnviado(true);
  };

  if (enviado) return (
    <div style={{ minHeight: "100vh", background: "#f0f4f8", fontFamily: "Arial" }}>
      <Navbar client={client} onLogout={logout} />
      <div style={{ maxWidth: "600px", margin: "80px auto", background: "white", borderRadius: "12px", padding: "40px", textAlign: "center", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
        <div style={{ fontSize: "64px", marginBottom: "16px" }}>✅</div>
        <h2 style={{ fontSize: "24px", fontWeight: "700", marginBottom: "8px" }}>Check-in Enviado!</h2>
        <p style={{ color: "#6b7280", marginBottom: "24px" }}>Seu treinador vai analisar e responder em breve.</p>
        <button onClick={() => navigate("/dashboard")} style={{ background: "#2563eb", color: "white", border: "none", padding: "12px 24px", borderRadius: "8px", cursor: "pointer", fontWeight: "600" }}>Voltar ao Dashboard</button>
      </div>
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: "#f0f4f8", fontFamily: "Arial" }}>
      <Navbar client={client} onLogout={logout} />
      <main style={{ maxWidth: "600px", margin: "0 auto", padding: "32px 16px" }}>
        <h2 style={{ fontSize: "24px", fontWeight: "700", marginBottom: "8px" }}>📋 Check-in Semanal</h2>
        <p style={{ color: "#6b7280", marginBottom: "24px" }}>Como foi sua semana?</p>
        <form onSubmit={handleSubmit} style={{ background: "white", borderRadius: "12px", padding: "32px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Voce treinou essa semana?</label>
            <div style={{ display: "flex", gap: "12px" }}>
              {["Sim, todos os dias", "Sim, alguns dias", "Nao treinei"].map(op => (
                <label key={op} style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                  <input type="radio" name="treinou" value={op} onChange={e => setForm({...form, treinou: e.target.value})} required />
                  {op}
                </label>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Seguiu a alimentacao?</label>
            <div style={{ display: "flex", gap: "12px" }}>
              {["Sim", "Parcialmente", "Nao"].map(op => (
                <label key={op} style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                  <input type="radio" name="seguiu_dieta" value={op} onChange={e => setForm({...form, seguiu_dieta: e.target.value})} required />
                  {op}
                </label>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Peso atual (kg)</label>
            <input type="number" step="0.1" placeholder="Ex: 70.5" value={form.peso} onChange={e => setForm({...form, peso: e.target.value})}
              style={{ width: "100%", padding: "10px", border: "1px solid #d1d5db", borderRadius: "8px", boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Teve alguma dificuldade?</label>
            <input type="text" placeholder="Ex: Fome a noite, dor no joelho..." value={form.dificuldade} onChange={e => setForm({...form, dificuldade: e.target.value})}
              style={{ width: "100%", padding: "10px", border: "1px solid #d1d5db", borderRadius: "8px", boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: "24px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Observacoes gerais</label>
            <textarea placeholder="Como voce esta se sentindo?" value={form.observacoes} onChange={e => setForm({...form, observacoes: e.target.value})}
              style={{ width: "100%", padding: "10px", border: "1px solid #d1d5db", borderRadius: "8px", boxSizing: "border-box", height: "100px", resize: "vertical" }} />
          </div>
          <button type="submit" style={{ width: "100%", padding: "14px", background: "#2563eb", color: "white", border: "none", borderRadius: "8px", fontSize: "16px", fontWeight: "600", cursor: "pointer" }}>
            Enviar Check-in
          </button>
        </form>
      </main>
    </div>
  );
}

// ─── ADMIN LOGIN ──────────────────────────────────────────────────────────────

function AdminLogin() {
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(API + "/admin/leads", {
        headers: { "x-api-key": apiKey },
      });
      if (res.ok) {
        localStorage.setItem("adminKey", apiKey);
        navigate("/admin/dashboard");
      } else {
        setError("Chave inválida. Verifique e tente novamente.");
      }
    } catch {
      setError("Erro ao conectar com o servidor.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0f172a", fontFamily: "Arial" }}>
      <div style={{ background: "#1e293b", padding: "48px 40px", borderRadius: "16px", width: "380px", border: "1px solid #334155" }}>
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <div style={{ fontSize: "36px", marginBottom: "12px" }}>🔐</div>
          <h1 style={{ fontSize: "24px", fontWeight: "700", color: "white" }}>Painel Admin</h1>
          <p style={{ color: "#64748b", marginTop: "8px", fontSize: "14px" }}>Sotel Fit Core</p>
        </div>
        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: "24px" }}>
            <label style={{ display: "block", marginBottom: "8px", fontWeight: "500", color: "#94a3b8", fontSize: "14px" }}>Chave de acesso</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="••••••••••••••••"
              required
              style={{ width: "100%", padding: "12px", background: "#0f172a", border: "1px solid #334155", borderRadius: "8px", fontSize: "14px", color: "white", boxSizing: "border-box" }}
            />
          </div>
          {error && <p style={{ color: "#f87171", fontSize: "13px", marginBottom: "16px" }}>{error}</p>}
          <button type="submit" disabled={loading} style={{ width: "100%", padding: "12px", background: "#2563eb", color: "white", border: "none", borderRadius: "8px", fontSize: "16px", fontWeight: "600", cursor: "pointer" }}>
            {loading ? "Verificando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}

// ─── ADMIN DASHBOARD ──────────────────────────────────────────────────────────

function AdminDashboard() {
  const navigate = useNavigate();
  const apiKey = localStorage.getItem("adminKey");
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);

  if (!apiKey) return <Navigate to="/admin" />;

  const headers = { "x-api-key": apiKey, "Content-Type": "application/json" };

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const res = await fetch(API + "/admin/leads", { headers });
      const data = await res.json();
      setLeads(Array.isArray(data) ? data : []);
    } catch {
      setMsg({ text: "Erro ao carregar leads.", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLeads(); }, []);

  const activateLead = async (phone: string) => {
    setActionLoading(phone + "_activate");
    try {
      const res = await fetch(API + "/admin/twilio/activate-lead", {
        method: "POST",
        headers,
        body: JSON.stringify({ phone }),
      });
      const data = await res.json();
      setMsg({ text: data.message || "Lead ativado!", type: "success" });
      fetchLeads();
    } catch {
      setMsg({ text: "Erro ao ativar lead.", type: "error" });
    } finally {
      setActionLoading(null);
    }
  };

  const releasePlan = async (phone: string) => {
    setActionLoading(phone + "_release");
    try {
      const res = await fetch(API + "/admin/twilio/release-plan", {
        method: "POST",
        headers,
        body: JSON.stringify({ phone }),
      });
      const data = await res.json();
      setMsg({ text: data.message || "Plano liberado!", type: "success" });
      fetchLeads();
    } catch {
      setMsg({ text: "Erro ao liberar plano.", type: "error" });
    } finally {
      setActionLoading(null);
    }
  };

  const logout = () => { localStorage.removeItem("adminKey"); navigate("/admin"); };

  const statusColor: Record<string, string> = {
    active: "#22c55e",
    active_client: "#3b82f6",
    onboarding_pending: "#f59e0b",
    lead: "#94a3b8",
  };

  const statusLabel: Record<string, string> = {
    active: "Ativo",
    active_client: "Cliente ativo",
    onboarding_pending: "Aguardando onboarding",
    lead: "Lead",
  };

  return (
    <div style={{ minHeight: "100vh", background: "#0f172a", fontFamily: "Arial", color: "white" }}>

      {/* Navbar Admin */}
      <nav style={{ background: "#1e293b", borderBottom: "1px solid #334155", padding: "16px 32px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "20px" }}>⚡</span>
          <h1 style={{ fontSize: "18px", fontWeight: "700" }}>Sotel Fit — Admin</h1>
        </div>
        <button onClick={logout} style={{ background: "transparent", color: "#94a3b8", border: "1px solid #334155", padding: "8px 16px", borderRadius: "6px", cursor: "pointer", fontSize: "13px" }}>
          Sair
        </button>
      </nav>

      <main style={{ maxWidth: "1200px", margin: "0 auto", padding: "32px 16px" }}>

        {/* Mensagem de feedback */}
        {msg && (
          <div style={{ background: msg.type === "success" ? "#14532d" : "#7f1d1d", border: `1px solid ${msg.type === "success" ? "#22c55e" : "#ef4444"}`, borderRadius: "8px", padding: "12px 16px", marginBottom: "24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "14px" }}>{msg.text}</span>
            <button onClick={() => setMsg(null)} style={{ background: "transparent", border: "none", color: "white", cursor: "pointer", fontSize: "16px" }}>×</button>
          </div>
        )}

        {/* Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px", marginBottom: "32px" }}>
          {[
            { label: "Total de leads", value: leads.length, icon: "👥" },
            { label: "Clientes ativos", value: leads.filter(l => l.status === "active_client" || l.status === "active").length, icon: "✅" },
            { label: "Aguardando onboarding", value: leads.filter(l => l.status === "onboarding_pending").length, icon: "⏳" },
          ].map((s, i) => (
            <div key={i} style={{ background: "#1e293b", borderRadius: "12px", padding: "24px", border: "1px solid #334155" }}>
              <div style={{ fontSize: "28px", marginBottom: "8px" }}>{s.icon}</div>
              <p style={{ color: "#64748b", fontSize: "12px", marginBottom: "4px" }}>{s.label}</p>
              <p style={{ fontSize: "32px", fontWeight: "700" }}>{s.value}</p>
            </div>
          ))}
        </div>

        {/* Tabela de Leads */}
        <div style={{ background: "#1e293b", borderRadius: "12px", border: "1px solid #334155", overflow: "hidden" }}>
          <div style={{ padding: "20px 24px", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ fontSize: "16px", fontWeight: "700" }}>📋 Leads e Clientes</h2>
            <button onClick={fetchLeads} style={{ background: "#334155", color: "white", border: "none", padding: "8px 14px", borderRadius: "6px", cursor: "pointer", fontSize: "13px" }}>
              🔄 Atualizar
            </button>
          </div>

          {loading ? (
            <div style={{ padding: "48px", textAlign: "center", color: "#64748b" }}>Carregando...</div>
          ) : leads.length === 0 ? (
            <div style={{ padding: "48px", textAlign: "center", color: "#64748b" }}>Nenhum lead encontrado.</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "#0f172a" }}>
                    {["Telefone", "Nome", "Objetivo", "Status", "Link enviado", "Data", "Ações"].map(h => (
                      <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", color: "#64748b", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {leads.map((lead, i) => (
                    <tr key={i} style={{ borderTop: "1px solid #334155" }}>
                      <td style={{ padding: "14px 16px", fontSize: "13px", color: "#94a3b8" }}>{lead.phone.replace("whatsapp:", "")}</td>
                      <td style={{ padding: "14px 16px", fontSize: "13px" }}>{lead.name || <span style={{ color: "#475569" }}>—</span>}</td>
                      <td style={{ padding: "14px 16px", fontSize: "13px" }}>{lead.goal || <span style={{ color: "#475569" }}>—</span>}</td>
                      <td style={{ padding: "14px 16px" }}>
                        <span style={{ background: statusColor[lead.status] + "22", color: statusColor[lead.status] || "#94a3b8", padding: "4px 10px", borderRadius: "20px", fontSize: "12px", fontWeight: "600" }}>
                          {statusLabel[lead.status] || lead.status}
                        </span>
                      </td>
                      <td style={{ padding: "14px 16px", fontSize: "13px" }}>
                        {lead.onboarding_link_sent ? <span style={{ color: "#22c55e" }}>✓ Sim</span> : <span style={{ color: "#475569" }}>Não</span>}
                      </td>
                      <td style={{ padding: "14px 16px", fontSize: "12px", color: "#64748b" }}>
                        {new Date(lead.created_at).toLocaleDateString("pt-BR")}
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        <div style={{ display: "flex", gap: "8px" }}>
                          {!lead.onboarding_link_sent && (
                            <button
                              onClick={() => activateLead(lead.phone)}
                              disabled={actionLoading === lead.phone + "_activate"}
                              style={{ background: "#1d4ed8", color: "white", border: "none", padding: "6px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600", whiteSpace: "nowrap" }}
                            >
                              {actionLoading === lead.phone + "_activate" ? "..." : "📲 Ativar"}
                            </button>
                          )}
                          {(lead.status === "active_client" || lead.status === "onboarding_pending") && (
                            <button
                              onClick={() => releasePlan(lead.phone)}
                              disabled={actionLoading === lead.phone + "_release"}
                              style={{ background: "#15803d", color: "white", border: "none", padding: "6px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600", whiteSpace: "nowrap" }}
                            >
                              {actionLoading === lead.phone + "_release" ? "..." : "🚀 Liberar plano"}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// ─── APP ──────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/checkin" element={<Checkin />} />
        <Route path="/admin" element={<AdminLogin />} />
        <Route path="/admin/dashboard" element={<AdminDashboard />} />
        <Route path="/" element={<Navigate to="/login" />} />
      </Routes>
    </BrowserRouter>
  );
}
