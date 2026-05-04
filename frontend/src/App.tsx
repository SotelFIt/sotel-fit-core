import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

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

function Onboarding() {
  const navigate = useNavigate();
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
      <input
        type={type} name={name} placeholder={placeholder}
        value={(form as any)[name]} onChange={handleChange} required
        style={{ width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", boxSizing: "border-box" }}
      />
    </div>
  );

  const textarea = (label: string, name: string, placeholder = "") => (
    <div style={{ marginBottom: "16px" }}>
      <label style={{ display: "block", fontWeight: "600", marginBottom: "6px", color: "#374151", fontSize: "14px" }}>{label}</label>
      <textarea
        name={name} placeholder={placeholder}
        value={(form as any)[name]} onChange={handleChange}
        style={{ width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", boxSizing: "border-box", height: "80px", resize: "vertical" }}
      />
    </div>
  );

  const select = (label: string, name: string, options: string[]) => (
    <div style={{ marginBottom: "16px" }}>
      <label style={{ display: "block", fontWeight: "600", marginBottom: "6px", color: "#374151", fontSize: "14px" }}>{label}</label>
      <select
        name={name} value={(form as any)[name]} onChange={handleChange} required
        style={{ width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", boxSizing: "border-box" }}
      >
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
          {textarea("Observações adicionais", "observacoes", "Alguma informação extra que queira compartilhar?")}

          <button type="submit" disabled={loading} style={{ width: "100%", padding: "14px", background: "#2563eb", color: "white", border: "none", borderRadius: "8px", fontSize: "16px", fontWeight: "700", cursor: "pointer", marginTop: "8px" }}>
            {loading ? "Enviando..." : "Enviar meu cadastro ✓"}
          </button>
        </form>
      </main>
    </div>
  );
}

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
            <input type="number" step="0.1" placeholder="Ex: 70.5" value={form.peso} onChange={e => setForm({...form, peso: e.target.value})} style={{ width: "100%", padding: "10px", border: "1px solid #d1d5db", borderRadius: "8px", boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Teve alguma dificuldade?</label>
            <input type="text" placeholder="Ex: Fome a noite, dor no joelho..." value={form.dificuldade} onChange={e => setForm({...form, dificuldade: e.target.value})} style={{ width: "100%", padding: "10px", border: "1px solid #d1d5db", borderRadius: "8px", boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: "24px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Observacoes gerais</label>
            <textarea placeholder="Como voce esta se sentindo?" value={form.observacoes} onChange={e => setForm({...form, observacoes: e.target.value})} style={{ width: "100%", padding: "10px", border: "1px solid #d1d5db", borderRadius: "8px", boxSizing: "border-box", height: "100px", resize: "vertical" }} />
          </div>
          <button type="submit" style={{ width: "100%", padding: "14px", background: "#2563eb", color: "white", border: "none", borderRadius: "8px", fontSize: "16px", fontWeight: "600", cursor: "pointer" }}>
            Enviar Check-in
          </button>
        </form>
      </main>
    </div>
  );
}

export default function App() {
  return (notepad models\onboarding.py
    <BrowserRouter>
      <Routes>
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/checkin" element={<Checkin />} />
        <Route path="/" element={<Navigate to="/login" />} />
      </Routes>
    </BrowserRouter>
  );
}