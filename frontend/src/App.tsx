import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

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

interface Onboarding {
  id: number;
  phone: string | null;
  nome: string | null;
  email: string | null;
  telefone: string | null;
  idade: string | null;
  peso: string | null;
  altura: string | null;
  objetivo: string | null;
  nivel_treino: string | null;
  dias_treino: string | null;
  horario_treino: string | null;
  lesoes: string | null;
  alimentacao_atual: string | null;
  maior_dificuldade: string | null;
  meta_principal: string | null;
  observacoes: string | null;
  created_at: string;
}

interface ClientInfo {
  id: number;
  name: string;
  phone: string;
  objective: string | null;
  status: string;
}

interface ClientData {
  client: {
    id: number;
    name: string;
    email: string | null;
    phone: string;
    objective: string | null;
    status: string;
  };
  onboarding: {
    nome: string | null;
    objetivo: string | null;
    nivel_treino: string | null;
    dias_treino: string | null;
    meta_principal: string | null;
  } | null;
  plan: { id: number; content: string | null; created_at: string } | null;
  diet: { id: number; content: string | null; created_at: string } | null;
}

function normalize_phone(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  const withCountry = digits.startsWith("55") ? digits : "55" + digits;
  return `whatsapp:+${withCountry}`;
}

function Navbar({ name, onLogout }: { name: string; onLogout: () => void }) {
  const navigate = useNavigate();
  return (
    <nav style={{ background: "#2563eb", color: "white", padding: "16px 32px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <h1 onClick={() => navigate("/dashboard")} style={{ fontSize: "22px", fontWeight: "700", cursor: "pointer" }}>Sotel Fit</h1>
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <span onClick={() => navigate("/checkin")} style={{ fontSize: "14px", cursor: "pointer", opacity: 0.8 }}>Check-in</span>
        <span style={{ fontSize: "14px" }}>{name}</span>
        <button onClick={onLogout} style={{ background: "white", color: "#2563eb", border: "none", padding: "8px 16px", borderRadius: "6px", cursor: "pointer", fontWeight: "600" }}>Sair</button>
      </div>
    </nav>
  );
}

function OnboardingModal({ onboarding, onClose }: { onboarding: Onboarding | null; onClose: () => void }) {
  const field = (label: string, value: string | null) => value ? (
    <div style={{ marginBottom: "12px" }}>
      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "2px" }}>{label}</p>
      <p style={{ color: "white", fontSize: "14px" }}>{value}</p>
    </div>
  ) : null;

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "20px" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{ background: "#1e293b", borderRadius: "16px", maxWidth: "680px", width: "100%", border: "1px solid #334155", maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "24px 28px", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ color: "white", fontSize: "18px", fontWeight: "700" }}>
              {onboarding ? `🔋 Onboarding – ${onboarding.nome || "Sem nome"}` : "🔋 Onboarding não enviado"}
            </h2>
            {onboarding && <p style={{ color: "#64748b", fontSize: "12px", marginTop: "4px" }}>Enviado em {new Date(onboarding.created_at).toLocaleDateString("pt-BR")}</p>}
          </div>
          <button onClick={onClose} style={{ background: "#334155", color: "white", border: "none", padding: "8px 12px", borderRadius: "8px", cursor: "pointer", fontSize: "16px" }}>×</button>
        </div>
        <div style={{ padding: "24px 28px", overflowY: "auto" }}>
          {!onboarding ? (
            <div style={{ textAlign: "center", padding: "32px 0" }}>
              <div style={{ fontSize: "48px", marginBottom: "16px" }}>🔋</div>
              <p style={{ color: "#64748b" }}>Este lead ainda não preencheu o formulário de onboarding.</p>
            </div>
          ) : (
            <>
              <h3 style={{ color: "#3b82f6", fontSize: "13px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "16px" }}>Dados Pessoais</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
                {field("Nome", onboarding.nome)}
                {field("Email", onboarding.email)}
                {field("Telefone", onboarding.telefone)}
                {field("Idade", onboarding.idade ? onboarding.idade + " anos" : null)}
                {field("Peso", onboarding.peso ? onboarding.peso + " kg" : null)}
                {field("Altura", onboarding.altura ? onboarding.altura + " cm" : null)}
              </div>
              <div style={{ borderTop: "1px solid #334155", margin: "20px 0" }} />
              <h3 style={{ color: "#3b82f6", fontSize: "13px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "16px" }}>Objetivo e Rotina</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
                {field("Objetivo principal", onboarding.objetivo)}
                {field("Nível de treino", onboarding.nivel_treino)}
                {field("Dias de treino", onboarding.dias_treino)}
                {field("Horário", onboarding.horario_treino)}
              </div>
              <div style={{ borderTop: "1px solid #334155", margin: "20px 0" }} />
              <h3 style={{ color: "#3b82f6", fontSize: "13px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "16px" }}>Saúde e Alimentação</h3>
              {field("Lesões / restrições", onboarding.lesoes)}
              {field("Alimentação atual", onboarding.alimentacao_atual)}
              {field("Maior dificuldade", onboarding.maior_dificuldade)}
              {field("Meta principal", onboarding.meta_principal)}
              {field("Observações", onboarding.observacoes)}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function CheckinModal({ client, onClose, apiKey }: { client: ClientInfo; onClose: () => void; apiKey: string }) {
  const [checkins, setCheckins] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const headers = { "x-api-key": apiKey };

  useEffect(() => {
    fetch(API + `/admin/checkins/${client.id}`, { headers })
      .then(r => r.json())
      .then(data => setCheckins(Array.isArray(data) ? data : []))
      .catch(() => setCheckins([]))
      .finally(() => setLoading(false));
  }, [client.id]);

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "20px" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{ background: "#1e293b", borderRadius: "16px", maxWidth: "900px", width: "100%", border: "1px solid #334155", maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "24px 28px", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ color: "white", fontSize: "18px", fontWeight: "700" }}>📋 Check-ins – {client.name}</h2>
            <p style={{ color: "#64748b", fontSize: "12px", marginTop: "4px" }}>{checkins.length} registro(s)</p>
          </div>
          <button onClick={onClose} style={{ background: "#334155", color: "white", border: "none", padding: "8px 12px", borderRadius: "8px", cursor: "pointer", fontSize: "16px" }}>×</button>
        </div>
        <div style={{ padding: "24px 28px", overflowY: "auto" }}>
          {loading ? (
            <p style={{ color: "#64748b" }}>Carregando...</p>
          ) : checkins.length === 0 ? (
            <div style={{ textAlign: "center", padding: "32px 0" }}>
              <div style={{ fontSize: "48px", marginBottom: "12px" }}>📋</div>
              <p style={{ color: "#64748b" }}>Nenhum check-in registrado ainda.</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {checkins.map((ci, i) => (
                <div key={i} style={{ background: "#0f172a", borderRadius: "8px", padding: "16px", border: "1px solid #334155" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "12px" }}>
                    <div>
                      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Treinou</p>
                      <p style={{ color: "white", fontSize: "14px" }}>{ci.treinou || "–"}</p>
                    </div>
                    <div>
                      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Seguiu dieta</p>
                      <p style={{ color: "white", fontSize: "14px" }}>{ci.seguiu_dieta || "–"}</p>
                    </div>
                    <div>
                      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Peso</p>
                      <p style={{ color: "white", fontSize: "14px" }}>{ci.peso ? ci.peso + " kg" : "–"}</p>
                    </div>
                    <div>
                      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Data</p>
                      <p style={{ color: "white", fontSize: "14px" }}>{new Date(ci.created_at).toLocaleDateString("pt-BR")}</p>
                    </div>
                  </div>
                  {ci.dificuldade && (
                    <div style={{ marginBottom: "8px" }}>
                      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Dificuldade</p>
                      <p style={{ color: "#fbbf24", fontSize: "13px" }}>{ci.dificuldade}</p>
                    </div>
                  )}
                  {ci.observacoes && (
                    <div>
                      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Observações</p>
                      <p style={{ color: "#e5e7eb", fontSize: "13px" }}>{ci.observacoes}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PlanModal({ client, onClose, apiKey }: { client: ClientInfo; onClose: () => void; apiKey: string }) {
  const [treino, setTreino] = useState("");
  const [dieta, setDieta] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const headers = { "x-api-key": apiKey, "Content-Type": "application/json" };

  const savePlan = async () => {
    if (!treino.trim()) { setMsg({ text: "Preencha o plano de treino.", type: "error" }); return; }
    setLoading(true);
    try {
      const res = await fetch(API + `/admin/clients/${client.id}/save-plan`, {
        method: "POST", headers, body: JSON.stringify({ content: treino })
      });
      if (res.ok) setMsg({ text: "Treino salvo!", type: "success" });
      else setMsg({ text: "Erro ao salvar treino.", type: "error" });
    } catch { setMsg({ text: "Erro de conexão.", type: "error" }); }
    finally { setLoading(false); }
  };

  const saveDiet = async () => {
    if (!dieta.trim()) { setMsg({ text: "Preencha o plano alimentar.", type: "error" }); return; }
    setLoading(true);
    try {
      const res = await fetch(API + `/admin/clients/${client.id}/save-diet`, {
        method: "POST", headers, body: JSON.stringify({ content: dieta })
      });
      if (res.ok) setMsg({ text: "Dieta salva!", type: "success" });
      else setMsg({ text: "Erro ao salvar dieta.", type: "error" });
    } catch { setMsg({ text: "Erro de conexão.", type: "error" }); }
    finally { setLoading(false); }
  };

  const saveAll = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const [r1, r2] = await Promise.all([
        fetch(API + `/admin/clients/${client.id}/save-plan`, { method: "POST", headers, body: JSON.stringify({ content: treino }) }),
        fetch(API + `/admin/clients/${client.id}/save-diet`, { method: "POST", headers, body: JSON.stringify({ content: dieta }) }),
      ]);
      if (r1.ok && r2.ok) setMsg({ text: "Treino e dieta salvos com sucesso!", type: "success" });
      else setMsg({ text: "Erro ao salvar um dos planos.", type: "error" });
    } catch { setMsg({ text: "Erro de conexão.", type: "error" }); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "20px" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{ background: "#1e293b", borderRadius: "16px", maxWidth: "800px", width: "100%", border: "1px solid #334155", maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "24px 28px", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ color: "white", fontSize: "18px", fontWeight: "700" }}>🏋️ Montar Plano – {client.name}</h2>
            <p style={{ color: "#64748b", fontSize: "12px", marginTop: "4px" }}>Objetivo: {client.objective || "não informado"}</p>
          </div>
          <button onClick={onClose} style={{ background: "#334155", color: "white", border: "none", padding: "8px 12px", borderRadius: "8px", cursor: "pointer", fontSize: "16px" }}>×</button>
        </div>

        <div style={{ padding: "24px 28px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "20px" }}>
          {msg && (
            <div style={{ background: msg.type === "success" ? "#14532d" : "#7f1d1d", border: `1px solid ${msg.type === "success" ? "#22c55e" : "#ef4444"}`, borderRadius: "8px", padding: "10px 14px", color: "white", fontSize: "14px" }}>
              {msg.text}
            </div>
          )}

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <label style={{ color: "#94a3b8", fontSize: "13px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em" }}>💪 Plano de Treino</label>
              <button onClick={savePlan} disabled={loading} style={{ background: "#1d4ed8", color: "white", border: "none", padding: "6px 14px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600" }}>
                Salvar treino
              </button>
            </div>
            <textarea
              value={treino}
              onChange={(e) => setTreino(e.target.value)}
              placeholder={`Exemplo:\nSEGUNDA - Peito e Tríceps\nSupino reto: 4x10\nCrucifixo: 3x12\n\nTERÇA - Costas e Bíceps\nPuxada frontal: 4x10\n...`}
              style={{ width: "100%", height: "200px", background: "#0f172a", border: "1px solid #334155", borderRadius: "8px", padding: "12px", color: "white", fontSize: "13px", resize: "vertical", boxSizing: "border-box", fontFamily: "monospace", lineHeight: "1.5" }}
            />
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <label style={{ color: "#94a3b8", fontSize: "13px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em" }}>🥗 Plano Alimentar</label>
              <button onClick={saveDiet} disabled={loading} style={{ background: "#15803d", color: "white", border: "none", padding: "6px 14px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600" }}>
                Salvar dieta
              </button>
            </div>
            <textarea
              value={dieta}
              onChange={(e) => setDieta(e.target.value)}
              placeholder={`Exemplo:\nCAFÉ DA MANHÃ (7h)\n3 ovos mexidos\n2 fatias de pão integral\n1 banana\n\nALMOÇO (12h)\n150g de frango grelhado\nArroz integral + brócolis\n...`}
              style={{ width: "100%", height: "200px", background: "#0f172a", border: "1px solid #334155", borderRadius: "8px", padding: "12px", color: "white", fontSize: "13px", resize: "vertical", boxSizing: "border-box", fontFamily: "monospace", lineHeight: "1.5" }}
            />
          </div>

          <button onClick={saveAll} disabled={loading} style={{ width: "100%", padding: "14px", background: "#7c3aed", color: "white", border: "none", borderRadius: "8px", fontSize: "15px", fontWeight: "700", cursor: "pointer" }}>
            {loading ? "Salvando..." : "💾 Salvar treino + dieta e liberar para o cliente"}
          </button>
        </div>
      </div>
    </div>
  );
}

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
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
      });
      setStep("done");
    } catch { alert("Erro ao enviar. Tente novamente."); }
    finally { setLoading(false); }
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
        <p style={{ color: "#94a3b8", fontSize: "16px", marginBottom: "32px", lineHeight: "1.6" }}>Antes de liberar seu plano personalizado, precisamos conhecer sua rotina, objetivo e ponto de partida.</p>
        <button onClick={() => setStep("form")} style={{ width: "100%", padding: "16px", background: "#2563eb", color: "white", border: "none", borderRadius: "10px", fontSize: "18px", fontWeight: "700", cursor: "pointer" }}>Começar meu cadastro →</button>
      </div>
    </div>
  );

  if (step === "done") return (
    <div style={{ minHeight: "100vh", background: "#0f172a", display: "flex", alignItems: "center", justifyContent: "center", padding: "20px", fontFamily: "Arial" }}>
      <div style={{ maxWidth: "480px", width: "100%", textAlign: "center" }}>
        <div style={{ fontSize: "64px", marginBottom: "16px" }}>✅</div>
        <h2 style={{ fontSize: "26px", fontWeight: "700", color: "white", marginBottom: "12px" }}>Cadastro recebido!</h2>
        <p style={{ color: "#94a3b8", fontSize: "16px", lineHeight: "1.6" }}>Agora o time Sotel vai montar seu plano personalizado.<br />Assim que estiver pronto, você será avisado pelo WhatsApp.</p>
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
          <h2 style={{ fontSize: "20px", fontWeight: "700", marginBottom: "24px", color: "#1e40af" }}>🔋 Dados Pessoais</h2>
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

function Login() {
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const formatted = normalize_phone(phone);
      const res = await fetch(API + `/clients/by-phone/${encodeURIComponent(formatted)}`);
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem("clientPhone", formatted);
        localStorage.setItem("clientData", JSON.stringify(data));
        navigate("/dashboard");
      } else {
        setError("Número não encontrado. Verifique se completou o cadastro.");
      }
    } catch { setError("Erro ao conectar com o servidor."); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f4f8", fontFamily: "Arial" }}>
      <div style={{ background: "white", padding: "40px", borderRadius: "12px", boxShadow: "0 4px 20px rgba(0,0,0,0.1)", width: "380px" }}>
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <div style={{ fontSize: "40px", marginBottom: "12px" }}>💪</div>
          <h1 style={{ fontSize: "28px", fontWeight: "700", color: "#1e40af" }}>Sotel Fit</h1>
          <p style={{ color: "#6b7280", marginTop: "8px" }}>Digite seu WhatsApp para acessar</p>
        </div>
        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: "24px" }}>
            <label style={{ display: "block", marginBottom: "6px", fontWeight: "500", color: "#374151" }}>Número do WhatsApp</label>
            <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+55 17 99999-9999" required
              style={{ width: "100%", padding: "12px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "16px", boxSizing: "border-box" }} />
          </div>
          {error && <p style={{ color: "#ef4444", fontSize: "13px", marginBottom: "16px" }}>{error}</p>}
          <button type="submit" disabled={loading} style={{ width: "100%", padding: "12px", background: "#2563eb", color: "white", border: "none", borderRadius: "8px", fontSize: "16px", fontWeight: "600", cursor: "pointer" }}>
            {loading ? "Buscando..." : "Acessar meu plano"}
          </button>
        </form>
        <p style={{ textAlign: "center", marginTop: "20px", color: "#9ca3af", fontSize: "13px" }}>
          Ainda não tem cadastro?{" "}
          <span onClick={() => window.location.href = "/onboarding"} style={{ color: "#2563eb", cursor: "pointer", fontWeight: "600" }}>Fazer cadastro</span>
        </p>
      </div>
    </div>
  );
}

function Dashboard() {
  const navigate = useNavigate();
  const phone = localStorage.getItem("clientPhone");
  const [data, setData] = useState<ClientData | null>(null);
  const [loading, setLoading] = useState(true);

  if (!phone) return <Navigate to="/login" />;
  const logout = () => { localStorage.clear(); navigate("/login"); };

  useEffect(() => {
    fetch(API + `/clients/by-phone/${encodeURIComponent(phone)}/data`)
      .then(r => r.json()).then(d => setData(d)).catch(() => setData(null)).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div style={{ minHeight: "100vh", background: "#f0f4f8", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "Arial" }}>
      <p style={{ color: "#6b7280" }}>Carregando seu plano...</p>
    </div>
  );

  const client = data?.client;
  const onboarding = data?.onboarding;
  const plan = data?.plan;
  const diet = data?.diet;
  const firstName = client?.name?.split(" ")[0] || "Cliente";

  return (
    <div style={{ minHeight: "100vh", background: "#f0f4f8", fontFamily: "Arial" }}>
      <Navbar name={firstName} onLogout={logout} />
      <main style={{ maxWidth: "1100px", margin: "0 auto", padding: "32px 16px" }}>
        <h2 style={{ fontSize: "24px", fontWeight: "700", marginBottom: "8px" }}>Olá, {firstName}! 👋</h2>
        <p style={{ color: "#6b7280", marginBottom: "32px" }}>Aqui está um resumo do seu progresso</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", marginBottom: "32px" }}>
          {[
            { title: "Objetivo", value: onboarding?.objetivo || client?.objective || "–", icon: "🎯" },
            { title: "Nível", value: onboarding?.nivel_treino || "–", icon: "📊" },
            { title: "Dias de treino", value: onboarding?.dias_treino || "–", icon: "📅" },
            { title: "Status", value: client?.status === "onboarding_completed" ? "Aguardando plano" : client?.status === "active" ? "Ativo" : client?.status || "–", icon: "✅" },
          ].map((card, i) => (
            <div key={i} style={{ background: "white", borderRadius: "12px", padding: "20px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
              <div style={{ fontSize: "32px", marginBottom: "12px" }}>{card.icon}</div>
              <p style={{ color: "#6b7280", fontSize: "12px", marginBottom: "4px" }}>{card.title}</p>
              <p style={{ fontWeight: "700", fontSize: "15px" }}>{card.value}</p>
            </div>
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          <div style={{ background: "white", borderRadius: "12px", padding: "24px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
            <h3 style={{ fontWeight: "700", marginBottom: "16px", fontSize: "16px" }}>💪 Plano de Treino</h3>
            {plan?.content ? (
              <div style={{ color: "#374151", fontSize: "14px", lineHeight: "1.6", whiteSpace: "pre-wrap" }}>{plan.content}</div>
            ) : (
              <div style={{ textAlign: "center", padding: "24px 0" }}>
                <div style={{ fontSize: "40px", marginBottom: "12px" }}>⏳</div>
                <p style={{ color: "#6b7280", fontSize: "14px" }}>Seu treinador está montando seu plano.</p>
                <p style={{ color: "#9ca3af", fontSize: "13px", marginTop: "8px" }}>Você será avisado pelo WhatsApp quando estiver pronto.</p>
              </div>
            )}
          </div>
          <div style={{ background: "white", borderRadius: "12px", padding: "24px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
            <h3 style={{ fontWeight: "700", marginBottom: "16px", fontSize: "16px" }}>🥗 Plano Alimentar</h3>
            {diet?.content ? (
              <div style={{ color: "#374151", fontSize: "14px", lineHeight: "1.6", whiteSpace: "pre-wrap" }}>{diet.content}</div>
            ) : (
              <div style={{ textAlign: "center", padding: "24px 0" }}>
                <div style={{ fontSize: "40px", marginBottom: "12px" }}>⏳</div>
                <p style={{ color: "#6b7280", fontSize: "14px" }}>Seu plano alimentar será montado em breve.</p>
              </div>
            )}
          </div>
        </div>
        <div style={{ background: "white", borderRadius: "12px", padding: "24px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)", marginTop: "16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h3 style={{ fontWeight: "700", marginBottom: "4px" }}>📋 Check-in Semanal</h3>
            <p style={{ color: "#6b7280", fontSize: "14px" }}>Responda como foi sua semana para seu treinador acompanhar.</p>
          </div>
          <button onClick={() => navigate("/checkin")} style={{ background: "#2563eb", color: "white", border: "none", padding: "12px 24px", borderRadius: "8px", cursor: "pointer", fontWeight: "600", whiteSpace: "nowrap" }}>Fazer Check-in</button>
        </div>
        {onboarding?.meta_principal && (
          <div style={{ background: "#eff6ff", borderRadius: "12px", padding: "20px", marginTop: "16px", border: "1px solid #bfdbfe" }}>
            <p style={{ color: "#1e40af", fontSize: "13px", fontWeight: "600", marginBottom: "4px" }}>SUA META</p>
            <p style={{ color: "#1e3a8a", fontSize: "15px" }}>"{onboarding.meta_principal}"</p>
          </div>
        )}
      </main>
    </div>
  );
}

function Checkin() {
  const navigate = useNavigate();
  const phone = localStorage.getItem("clientPhone");
  const clientDataRaw = localStorage.getItem("clientData");
  const clientData = clientDataRaw ? JSON.parse(clientDataRaw) : null;
  const [form, setForm] = useState({ treinou: "", seguiu_dieta: "", peso: "", dificuldade: "", observacoes: "" });
  const [enviado, setEnviado] = useState(false);

  if (!phone) return <Navigate to="/login" />;
  const logout = () => { localStorage.clear(); navigate("/login"); };
  const firstName = clientData?.name?.split(" ")[0] || "Cliente";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientData?.id) return;
    try {
      await fetch(API + "/admin/checkin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientData.id,
          treinou: form.treinou,
          seguiu_dieta: form.seguiu_dieta,
          peso: form.peso ? parseFloat(form.peso) : null,
          energia: null,
          dificuldade: form.dificuldade,
          observacoes: form.observacoes,
        }),
      });
    } catch (e) {
      console.error("Erro ao enviar check-in:", e);
    }
    setEnviado(true);
  };

  if (enviado) return (
    <div style={{ minHeight: "100vh", background: "#f0f4f8", fontFamily: "Arial" }}>
      <Navbar name={firstName} onLogout={logout} />
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
      <Navbar name={firstName} onLogout={logout} />
      <main style={{ maxWidth: "600px", margin: "0 auto", padding: "32px 16px" }}>
        <h2 style={{ fontSize: "24px", fontWeight: "700", marginBottom: "8px" }}>📋 Check-in Semanal</h2>
        <p style={{ color: "#6b7280", marginBottom: "24px" }}>Como foi sua semana?</p>
        <form onSubmit={handleSubmit} style={{ background: "white", borderRadius: "12px", padding: "32px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Você treinou essa semana?</label>
            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
              {["Sim, todos os dias", "Sim, alguns dias", "Não treinei"].map(op => (
                <label key={op} style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                  <input type="radio" name="treinou" value={op} onChange={e => setForm({...form, treinou: e.target.value})} required />{op}
                </label>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Seguiu a alimentação?</label>
            <div style={{ display: "flex", gap: "12px" }}>
              {["Sim", "Parcialmente", "Não"].map(op => (
                <label key={op} style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                  <input type="radio" name="seguiu_dieta" value={op} onChange={e => setForm({...form, seguiu_dieta: e.target.value})} required />{op}
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
            <input type="text" placeholder="Ex: Fome à noite, dor no joelho..." value={form.dificuldade} onChange={e => setForm({...form, dificuldade: e.target.value})}
              style={{ width: "100%", padding: "10px", border: "1px solid #d1d5db", borderRadius: "8px", boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: "24px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Observações gerais</label>
            <textarea placeholder="Como você está se sentindo?" value={form.observacoes} onChange={e => setForm({...form, observacoes: e.target.value})}
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
      const res = await fetch(API + "/admin/leads", { headers: { "x-api-key": apiKey } });
      if (res.ok) { localStorage.setItem("adminKey", apiKey); navigate("/admin/dashboard"); }
      else setError("Chave inválida. Verifique e tente novamente.");
    } catch { setError("Erro ao conectar com o servidor."); }
    finally { setLoading(false); }
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
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="•••••••••••••••" required
              style={{ width: "100%", padding: "12px", background: "#0f172a", border: "1px solid #334155", borderRadius: "8px", fontSize: "14px", color: "white", boxSizing: "border-box" }} />
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

function AdminDashboard() {
  const navigate = useNavigate();
  const apiKey = localStorage.getItem("adminKey");
  const [leads, setLeads] = useState<Lead[]>([]);
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [modalState, setModalState] = useState<"closed" | "loading" | "open">("closed");
  const [modalData, setModalData] = useState<Onboarding | null>(null);
  const [planModal, setPlanModal] = useState<ClientInfo | null>(null);
  const [checkinModal, setCheckinModal] = useState<ClientInfo | null>(null);

  if (!apiKey) return <Navigate to="/admin" />;
  const headers = { "x-api-key": apiKey, "Content-Type": "application/json" };

  const fetchData = async () => {
    setLoading(true);
    try {
      const [leadsRes, clientsRes] = await Promise.all([
        fetch(API + "/admin/leads", { headers }),
        fetch(API + "/admin/clients", { headers }),
      ]);
      const leadsData = await leadsRes.json();
      const clientsData = await clientsRes.json();
      setLeads(Array.isArray(leadsData) ? leadsData : []);
      setClients(Array.isArray(clientsData) ? clientsData : []);
    } catch { setMsg({ text: "Erro ao carregar dados.", type: "error" }); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, []);

  const viewOnboarding = async (phone: string) => {
    setModalState("loading");
    setModalData(null);
    try {
      const res = await fetch(API + `/admin/onboardings/by-phone/${encodeURIComponent(phone)}`, { headers });
      const data = await res.json();
      setModalData(data || null);
    } catch { setModalData(null); }
    finally { setModalState("open"); }
  };

  const activateLead = async (phone: string) => {
    setActionLoading(phone + "_activate");
    try {
      const res = await fetch(API + "/admin/twilio/activate-lead", { method: "POST", headers, body: JSON.stringify({ phone }) });
      const data = await res.json();
      setMsg({ text: data.message || "Lead ativado!", type: "success" });
      fetchData();
    } catch { setMsg({ text: "Erro ao ativar lead.", type: "error" }); }
    finally { setActionLoading(null); }
  };

  const releasePlan = async (phone: string) => {
    setActionLoading(phone + "_release");
    try {
      const res = await fetch(API + "/admin/twilio/release-plan", { method: "POST", headers, body: JSON.stringify({ phone }) });
      const data = await res.json();
      setMsg({ text: data.message || "Plano liberado!", type: "success" });
      fetchData();
    } catch { setMsg({ text: "Erro ao liberar plano.", type: "error" }); }
    finally { setActionLoading(null); }
  };

  const logout = () => { localStorage.removeItem("adminKey"); navigate("/admin"); };

  const statusColor: Record<string, string> = {
    active: "#22c55e", active_client: "#3b82f6",
    onboarding_pending: "#f59e0b", onboarding_completed: "#a855f7", lead: "#94a3b8",
  };
  const statusLabel: Record<string, string> = {
    active: "Ativo", active_client: "Cliente ativo",
    onboarding_pending: "Aguardando onboarding", onboarding_completed: "Onboarding feito", lead: "Lead",
  };

  return (
    <div style={{ minHeight: "100vh", background: "#0f172a", fontFamily: "Arial", color: "white" }}>
      {modalState === "loading" && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ color: "white", fontSize: "18px" }}>Carregando...</div>
        </div>
      )}
      {modalState === "open" && <OnboardingModal onboarding={modalData} onClose={() => setModalState("closed")} />}
      {planModal && <PlanModal client={planModal} onClose={() => setPlanModal(null)} apiKey={apiKey} />}
      {checkinModal && <CheckinModal client={checkinModal} onClose={() => setCheckinModal(null)} apiKey={apiKey} />}

      <nav style={{ background: "#1e293b", borderBottom: "1px solid #334155", padding: "16px 32px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "20px" }}>⚡</span>
          <h1 style={{ fontSize: "18px", fontWeight: "700" }}>Sotel Fit – Admin</h1>
        </div>
        <button onClick={logout} style={{ background: "transparent", color: "#94a3b8", border: "1px solid #334155", padding: "8px 16px", borderRadius: "6px", cursor: "pointer", fontSize: "13px" }}>Sair</button>
      </nav>

      <main style={{ maxWidth: "1200px", margin: "0 auto", padding: "32px 16px" }}>
        {msg && (
          <div style={{ background: msg.type === "success" ? "#14532d" : "#7f1d1d", border: `1px solid ${msg.type === "success" ? "#22c55e" : "#ef4444"}`, borderRadius: "8px", padding: "12px 16px", marginBottom: "24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "14px" }}>{msg.text}</span>
            <button onClick={() => setMsg(null)} style={{ background: "transparent", border: "none", color: "white", cursor: "pointer", fontSize: "16px" }}>×</button>
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px", marginBottom: "32px" }}>
          {[
            { label: "Total de leads", value: leads.length, icon: "👥" },
            { label: "Clientes ativos", value: leads.filter(l => l.status === "active_client" || l.status === "active").length, icon: "✅" },
            { label: "Onboarding feito", value: leads.filter(l => l.status === "onboarding_completed").length, icon: "📋" },
          ].map((s, i) => (
            <div key={i} style={{ background: "#1e293b", borderRadius: "12px", padding: "24px", border: "1px solid #334155" }}>
              <div style={{ fontSize: "28px", marginBottom: "8px" }}>{s.icon}</div>
              <p style={{ color: "#64748b", fontSize: "12px", marginBottom: "4px" }}>{s.label}</p>
              <p style={{ fontSize: "32px", fontWeight: "700" }}>{s.value}</p>
            </div>
          ))}
        </div>

        {/* Clientes com plano */}
        {clients.length > 0 && (
          <div style={{ background: "#1e293b", borderRadius: "12px", border: "1px solid #334155", overflow: "hidden", marginBottom: "24px" }}>
            <div style={{ padding: "20px 24px", borderBottom: "1px solid #334155" }}>
              <h2 style={{ fontSize: "16px", fontWeight: "700" }}>🏋️ Montar Treino e Dieta</h2>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "#0f172a" }}>
                    {["Nome", "Telefone", "Objetivo", "Status", "Ação"].map(h => (
                      <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", color: "#64748b", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {clients.map((client, i) => (
                    <tr key={i} style={{ borderTop: "1px solid #334155" }}>
                      <td style={{ padding: "14px 16px", fontSize: "13px", fontWeight: "600" }}>{client.name || "–"}</td>
                      <td style={{ padding: "14px 16px", fontSize: "13px", color: "#94a3b8" }}>{client.phone?.replace("whatsapp:", "") || "–"}</td>
                      <td style={{ padding: "14px 16px", fontSize: "13px" }}>{client.objective || "–"}</td>
                      <td style={{ padding: "14px 16px", fontSize: "13px" }}>
                        <span style={{ background: "#1e3a5f", color: "#93c5fd", padding: "3px 8px", borderRadius: "12px", fontSize: "11px" }}>{client.status}</span>
                      </td>
                      <td style={{ padding: "14px 16px", display: "flex", gap: "6px", flexWrap: "wrap" }}>
                        <button onClick={() => setPlanModal(client)}
                          style={{ background: "#7c3aed", color: "white", border: "none", padding: "8px 16px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600" }}>
                          🏋️ Plano
                        </button>
                        <button onClick={() => setCheckinModal(client)}
                          style={{ background: "#1d4ed8", color: "white", border: "none", padding: "8px 16px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600" }}>
                          📋 Check-ins
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tabela de Leads */}
        <div style={{ background: "#1e293b", borderRadius: "12px", border: "1px solid #334155", overflow: "hidden" }}>
          <div style={{ padding: "20px 24px", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ fontSize: "16px", fontWeight: "700" }}>📋 Leads e Clientes</h2>
            <button onClick={fetchData} style={{ background: "#334155", color: "white", border: "none", padding: "8px 14px", borderRadius: "6px", cursor: "pointer", fontSize: "13px" }}>🔄 Atualizar</button>
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
                      <td style={{ padding: "14px 16px", fontSize: "13px" }}>{lead.name || <span style={{ color: "#475569" }}>–</span>}</td>
                      <td style={{ padding: "14px 16px", fontSize: "13px" }}>{lead.goal || <span style={{ color: "#475569" }}>–</span>}</td>
                      <td style={{ padding: "14px 16px" }}>
                        <span style={{ background: (statusColor[lead.status] || "#94a3b8") + "22", color: statusColor[lead.status] || "#94a3b8", padding: "4px 10px", borderRadius: "20px", fontSize: "12px", fontWeight: "600" }}>
                          {statusLabel[lead.status] || lead.status}
                        </span>
                      </td>
                      <td style={{ padding: "14px 16px", fontSize: "13px" }}>
                        {lead.onboarding_link_sent ? <span style={{ color: "#22c55e" }}>✓ Sim</span> : <span style={{ color: "#475569" }}>Não</span>}
                      </td>
                      <td style={{ padding: "14px 16px", fontSize: "12px", color: "#64748b" }}>{new Date(lead.created_at).toLocaleDateString("pt-BR")}</td>
                      <td style={{ padding: "14px 16px" }}>
                        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                          <button onClick={() => viewOnboarding(lead.phone)}
                            style={{ background: "#1e3a5f", color: "#93c5fd", border: "1px solid #1d4ed8", padding: "6px 10px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600", whiteSpace: "nowrap" }}>
                            📋 Onboarding
                          </button>
                          {!lead.onboarding_link_sent && (
                            <button onClick={() => activateLead(lead.phone)} disabled={actionLoading === lead.phone + "_activate"}
                              style={{ background: "#1d4ed8", color: "white", border: "none", padding: "6px 10px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600", whiteSpace: "nowrap" }}>
                              {actionLoading === lead.phone + "_activate" ? "..." : "📲 Ativar"}
                            </button>
                          )}
                          {(lead.status === "active_client" || lead.status === "onboarding_pending" || lead.status === "onboarding_completed") && (
                            <button onClick={() => releasePlan(lead.phone)} disabled={actionLoading === lead.phone + "_release"}
                              style={{ background: "#15803d", color: "white", border: "none", padding: "6px 10px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600", whiteSpace: "nowrap" }}>
                              {actionLoading === lead.phone + "_release" ? "..." : "🚀 Liberar"}
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