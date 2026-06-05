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

/* ─────────────────────────────────────────────
   ONBOARDING — 9 etapas inteligentes
───────────────────────────────────────────── */

const OB_ACCENT = "#00E87A";
const OB_BG = "#080d14";
const OB_CARD = "#111827";
const OB_BORDER = "#1f2937";
const OB_MUTED = "#6b7280";

function OptionBtn({
  label, icon, selected, onClick, wide = false,
}: { label: string; icon?: string; selected: boolean; onClick: () => void; wide?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: wide ? "14px 18px" : "12px 14px",
        background: selected ? `${OB_ACCENT}18` : OB_CARD,
        border: `1.5px solid ${selected ? OB_ACCENT : OB_BORDER}`,
        borderRadius: "10px",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        gap: "8px",
        color: selected ? OB_ACCENT : "#e5e7eb",
        fontSize: "13px",
        fontWeight: selected ? "600" : "400",
        transition: "all 0.15s",
        width: wide ? "100%" : "auto",
        textAlign: "left",
      }}
    >
      {icon && <span style={{ fontSize: "16px" }}>{icon}</span>}
      <span style={{ flex: 1 }}>{label}</span>
      {selected && <span style={{ marginLeft: "auto", fontSize: "12px" }}>✓</span>}
    </button>
  );
}

function OBInput({
  label, name, value, onChange, type = "text", placeholder = "", required = false,
}: {
  label: string; name: string; value: string;
  onChange: (v: string) => void; type?: string; placeholder?: string; required?: boolean;
}) {
  return (
    <div style={{ marginBottom: "16px" }}>
      <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "8px" }}>
        {label}{required && <span style={{ color: OB_ACCENT }}> *</span>}
      </label>
      <input
        type={type} name={name} value={value} placeholder={placeholder}
        onChange={e => onChange(e.target.value)}
        style={{
          width: "100%", padding: "12px 14px",
          background: OB_CARD, border: `1px solid ${OB_BORDER}`,
          borderRadius: "10px", fontSize: "15px", color: "white",
          boxSizing: "border-box", outline: "none",
        }}
      />
    </div>
  );
}

function OBTextarea({
  label, name, value, onChange, placeholder = "", hint = "",
}: { label: string; name: string; value: string; onChange: (v: string) => void; placeholder?: string; hint?: string }) {
  return (
    <div style={{ marginBottom: "16px" }}>
      <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "8px" }}>
        {label}
      </label>
      {hint && <p style={{ fontSize: "12px", color: "#4b5563", marginBottom: "8px", marginTop: "-4px" }}>{hint}</p>}
      <textarea
        name={name} value={value} placeholder={placeholder}
        onChange={e => onChange(e.target.value)}
        style={{
          width: "100%", padding: "12px 14px", height: "90px",
          background: OB_CARD, border: `1px solid ${OB_BORDER}`,
          borderRadius: "10px", fontSize: "14px", color: "white",
          boxSizing: "border-box", resize: "none", outline: "none", lineHeight: "1.5",
        }}
      />
    </div>
  );
}

function ProgressBar({ step, total }: { step: number; total: number }) {
  const pct = Math.round((step / total) * 100);
  return (
    <div style={{ marginBottom: "28px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <span style={{ fontSize: "11px", color: OB_MUTED, fontWeight: "600", letterSpacing: "0.08em", textTransform: "uppercase" }}>
          Etapa {step} de {total}
        </span>
        <span style={{ fontSize: "11px", color: OB_ACCENT, fontWeight: "700" }}>{pct}%</span>
      </div>
      <div style={{ height: "3px", background: OB_BORDER, borderRadius: "99px", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: OB_ACCENT, borderRadius: "99px", transition: "width 0.4s ease" }} />
      </div>
    </div>
  );
}

function StepHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div style={{ marginBottom: "24px" }}>
      <h2 style={{ fontSize: "20px", fontWeight: "700", color: "white", marginBottom: "6px", lineHeight: "1.3" }}>{title}</h2>
      <p style={{ fontSize: "14px", color: OB_MUTED, lineHeight: "1.5" }}>{subtitle}</p>
    </div>
  );
}

function NavBtns({
  onBack, onNext, nextLabel = "Próximo →", loading = false, canNext = true, isFirst = false,
}: { onBack: () => void; onNext: () => void; nextLabel?: string; loading?: boolean; canNext?: boolean; isFirst?: boolean }) {
  return (
    <div style={{ display: "flex", gap: "10px", marginTop: "28px" }}>
      {!isFirst && (
        <button type="button" onClick={onBack}
          style={{ padding: "13px 20px", background: "transparent", border: `1px solid ${OB_BORDER}`, borderRadius: "10px", color: OB_MUTED, fontSize: "14px", cursor: "pointer", fontWeight: "500" }}>
          ← Voltar
        </button>
      )}
      <button type="button" onClick={onNext} disabled={!canNext || loading}
        style={{
          flex: 1, padding: "13px 20px", background: canNext ? OB_ACCENT : "#1f2937",
          border: "none", borderRadius: "10px", color: canNext ? "#000" : OB_MUTED,
          fontSize: "15px", cursor: canNext ? "pointer" : "not-allowed", fontWeight: "700", transition: "all 0.15s",
        }}>
        {loading ? "Enviando..." : nextLabel}
      </button>
    </div>
  );
}

type FormState = {
  nome: string; email: string; telefone: string; idade: string; sexo: string;
  altura: string; peso: string; cidade: string;
  objetivo: string; meta_principal: string;
  nivel_treino: string; treinou_antes: string; tempo_parado: string;
  dias_treino: string; horario_treino: string; tempo_por_treino: string;
  tipo_trabalho: string; nivel_estresse: string; qualidade_sono: string;
  lesoes: string; dores: string; medicamentos: string;
  problemas_hormonais: string; problemas_cardiacos: string;
  refeicoes_dia: string; consome_alcool: string; bebe_agua: string;
  tem_compulsao: string; dificuldade_alimentar: string; alimentacao_atual: string;
  ambiente_treino: string; tem_equipamentos: string; cardio_disponivel: string;
  impedimento_principal: string; motivo_desistencia: string; expectativa: string;
};

function Onboarding() {
  const TOTAL = 9;
  const [screen, setScreen] = useState<"welcome" | "steps" | "done">("welcome");
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState<FormState>({
    nome: "", email: "", telefone: "", idade: "", sexo: "",
    altura: "", peso: "", cidade: "",
    objetivo: "", meta_principal: "",
    nivel_treino: "", treinou_antes: "", tempo_parado: "",
    dias_treino: "", horario_treino: "", tempo_por_treino: "",
    tipo_trabalho: "", nivel_estresse: "", qualidade_sono: "",
    lesoes: "", dores: "", medicamentos: "",
    problemas_hormonais: "", problemas_cardiacos: "",
    refeicoes_dia: "", consome_alcool: "", bebe_agua: "",
    tem_compulsao: "", dificuldade_alimentar: "", alimentacao_atual: "",
    ambiente_treino: "", tem_equipamentos: "", cardio_disponivel: "",
    impedimento_principal: "", motivo_desistencia: "", expectativa: "",
  });

  const set = (field: keyof FormState, value: string) =>
    setForm(f => ({ ...f, [field]: value }));

  const next = () => { if (step < TOTAL) setStep(s => s + 1); else handleSubmit(); };
  const back = () => { if (step > 1) setStep(s => s - 1); else setScreen("welcome"); };

  const handleSubmit = async () => {
    setLoading(true);
    const extra = {
      sexo: form.sexo, cidade: form.cidade, treinou_antes: form.treinou_antes,
      tempo_parado: form.tempo_parado, tempo_por_treino: form.tempo_por_treino,
      tipo_trabalho: form.tipo_trabalho, nivel_estresse: form.nivel_estresse,
      qualidade_sono: form.qualidade_sono, dores: form.dores,
      medicamentos: form.medicamentos, problemas_hormonais: form.problemas_hormonais,
      problemas_cardiacos: form.problemas_cardiacos, refeicoes_dia: form.refeicoes_dia,
      consome_alcool: form.consome_alcool, bebe_agua: form.bebe_agua,
      tem_compulsao: form.tem_compulsao, dificuldade_alimentar: form.dificuldade_alimentar,
      ambiente_treino: form.ambiente_treino, tem_equipamentos: form.tem_equipamentos,
      cardio_disponivel: form.cardio_disponivel, impedimento_principal: form.impedimento_principal,
      motivo_desistencia: form.motivo_desistencia, expectativa: form.expectativa,
    };
    const payload = {
      nome: form.nome, email: form.email, telefone: form.telefone,
      idade: form.idade, peso: form.peso, altura: form.altura,
      objetivo: form.objetivo, nivel_treino: form.nivel_treino,
      dias_treino: form.dias_treino, horario_treino: form.horario_treino,
      lesoes: form.lesoes || "Nenhuma", alimentacao_atual: form.alimentacao_atual,
      maior_dificuldade: form.dificuldade_alimentar || form.impedimento_principal,
      meta_principal: form.meta_principal,
      observacoes: JSON.stringify(extra),
    };
    try {
      await fetch(API + "/onboarding/lead", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setScreen("done");
    } catch { alert("Erro ao enviar. Tente novamente."); }
    finally { setLoading(false); }
  };

  const wrap = (children: React.ReactNode) => (
    <div style={{ minHeight: "100vh", background: OB_BG, fontFamily: "'DM Sans', 'Segoe UI', sans-serif", color: "white" }}>
      <div style={{ maxWidth: "480px", margin: "0 auto", padding: "0 0 40px" }}>
        {/* Header */}
        <div style={{ padding: "20px 24px 0", display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{ width: "28px", height: "28px", background: OB_ACCENT, borderRadius: "8px", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ fontSize: "14px", color: "#000", fontWeight: "800" }}>S</span>
          </div>
          <span style={{ fontSize: "14px", fontWeight: "600", color: "#9ca3af" }}>Sotel Fit Core</span>
        </div>
        <div style={{ padding: "24px 24px 0" }}>
          {screen === "steps" && <ProgressBar step={step} total={TOTAL} />}
          {children}
        </div>
      </div>
    </div>
  );

  // WELCOME
  if (screen === "welcome") return wrap(
    <div style={{ paddingTop: "32px" }}>
      <div style={{ width: "64px", height: "64px", background: `${OB_ACCENT}18`, borderRadius: "20px", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "24px", border: `1px solid ${OB_ACCENT}30` }}>
        <span style={{ fontSize: "28px" }}>💪</span>
      </div>
      <h1 style={{ fontSize: "28px", fontWeight: "800", lineHeight: "1.2", marginBottom: "12px" }}>
        Bem-vindo ao<br />
        <span style={{ color: OB_ACCENT }}>Sotel Fit Core</span>
      </h1>
      <p style={{ color: OB_MUTED, fontSize: "15px", lineHeight: "1.6", marginBottom: "12px" }}>
        Vamos conhecer você antes de montar seu plano personalizado.
      </p>
      <p style={{ color: "#374151", fontSize: "13px", lineHeight: "1.6", marginBottom: "36px" }}>
        São 9 etapas rápidas. Quanto mais preciso você for, melhor será o seu resultado.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "32px" }}>
        {["Treino personalizado para seu objetivo", "Dieta adaptada à sua rotina", "Acompanhamento inteligente"].map((item, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ color: OB_ACCENT, fontSize: "12px" }}>✓</span>
            <span style={{ color: "#9ca3af", fontSize: "14px" }}>{item}</span>
          </div>
        ))}
      </div>
      <button
        type="button" onClick={() => setScreen("steps")}
        style={{ width: "100%", padding: "16px", background: OB_ACCENT, border: "none", borderRadius: "12px", fontSize: "16px", fontWeight: "700", color: "#000", cursor: "pointer" }}>
        Começar meu cadastro →
      </button>
      <p style={{ textAlign: "center", color: "#374151", fontSize: "12px", marginTop: "16px" }}>
        Leva cerca de 3 minutos
      </p>
    </div>
  );

  // DONE
  if (screen === "done") return wrap(
    <div style={{ paddingTop: "48px", textAlign: "center" }}>
      <div style={{ width: "72px", height: "72px", background: `${OB_ACCENT}18`, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 24px", border: `2px solid ${OB_ACCENT}` }}>
        <span style={{ fontSize: "32px" }}>✅</span>
      </div>
      <h2 style={{ fontSize: "24px", fontWeight: "800", marginBottom: "12px" }}>Cadastro enviado!</h2>
      <p style={{ color: OB_MUTED, fontSize: "15px", lineHeight: "1.6", marginBottom: "32px" }}>
        Seu perfil foi registrado com sucesso.<br />
        O time Sotel vai montar seu plano personalizado e você será avisado pelo WhatsApp.
      </p>
      <div style={{ background: OB_CARD, border: `1px solid ${OB_BORDER}`, borderRadius: "12px", padding: "20px", textAlign: "left" }}>
        <p style={{ fontSize: "12px", color: OB_MUTED, fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "12px" }}>Próximos passos</p>
        {["Analisaremos seu perfil completo", "Montamos treino e dieta personalizados", "Você recebe acesso ao app pelo WhatsApp"].map((s, i) => (
          <div key={i} style={{ display: "flex", gap: "12px", alignItems: "flex-start", marginBottom: "10px" }}>
            <span style={{ minWidth: "20px", height: "20px", background: OB_ACCENT, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "10px", color: "#000", fontWeight: "700" }}>{i + 1}</span>
            <span style={{ fontSize: "13px", color: "#d1d5db", lineHeight: "1.4" }}>{s}</span>
          </div>
        ))}
      </div>
    </div>
  );

  // ─── ETAPA 1 — Identidade ───
  if (step === 1) return wrap(
    <>
      <StepHeader title="Quem é você?" subtitle="Dados básicos para personalizar seu plano." />
      <OBInput label="Nome completo" name="nome" value={form.nome} onChange={v => set("nome", v)} placeholder="Seu nome" required />
      <OBInput label="Email" name="email" value={form.email} onChange={v => set("email", v)} type="email" placeholder="seu@email.com" />
      <OBInput label="WhatsApp" name="telefone" value={form.telefone} onChange={v => set("telefone", v)} placeholder="+55 17 99999-9999" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
        <OBInput label="Idade" name="idade" value={form.idade} onChange={v => set("idade", v)} type="number" placeholder="Ex: 28" />
        <OBInput label="Cidade" name="cidade" value={form.cidade} onChange={v => set("cidade", v)} placeholder="Ex: São Paulo" />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
        <OBInput label="Peso (kg)" name="peso" value={form.peso} onChange={v => set("peso", v)} type="number" placeholder="Ex: 75" />
        <OBInput label="Altura (cm)" name="altura" value={form.altura} onChange={v => set("altura", v)} type="number" placeholder="Ex: 175" />
      </div>
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Sexo</label>
        <div style={{ display: "flex", gap: "8px" }}>
          {[["Masculino", "♂"], ["Feminino", "♀"], ["Prefiro não informar", "–"]].map(([label, icon]) => (
            <OptionBtn key={label} label={label} icon={icon} selected={form.sexo === label} onClick={() => set("sexo", label)} />
          ))}
        </div>
      </div>
      <NavBtns onBack={back} onNext={next} canNext={!!form.nome} isFirst />
    </>
  );

  // ─── ETAPA 2 — Objetivo ───
  if (step === 2) return wrap(
    <>
      <StepHeader title="Qual é seu objetivo?" subtitle="Isso define a estrutura do seu treino e dieta." />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "20px" }}>
        {[
          ["Emagrecimento", "🔥"], ["Hipertrofia", "💪"],
          ["Definição", "⚡"], ["Performance", "🏃"],
          ["Saúde geral", "❤️"], ["Condicionamento", "🫁"],
        ].map(([label, icon]) => (
          <OptionBtn key={label} label={label} icon={icon} selected={form.objetivo === label} onClick={() => set("objetivo", label)} />
        ))}
      </div>
      <OBTextarea
        label="Qual sua maior meta hoje?"
        name="meta_principal"
        value={form.meta_principal}
        onChange={v => set("meta_principal", v)}
        placeholder="Ex: Perder 10kg até o fim do ano, ganhar massa, melhorar condicionamento..."
        hint="Seja específico. Isso alimenta sua IA de acompanhamento."
      />
      <NavBtns onBack={back} onNext={next} canNext={!!form.objetivo} />
    </>
  );

  // ─── ETAPA 3 — Experiência ───
  if (step === 3) return wrap(
    <>
      <StepHeader title="Qual sua experiência?" subtitle="Para calibrar a intensidade certa desde o início." />
      <div style={{ marginBottom: "20px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Nível atual</label>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {[
            ["Iniciante", "Nunca treinei ou treinei pouco", "🌱"],
            ["Intermediário", "Treino há mais de 6 meses", "📈"],
            ["Avançado", "Treino consistente há mais de 2 anos", "🏆"],
          ].map(([nivel, desc, icon]) => (
            <button key={nivel} type="button" onClick={() => set("nivel_treino", nivel)}
              style={{
                padding: "14px 16px", background: form.nivel_treino === nivel ? `${OB_ACCENT}18` : OB_CARD,
                border: `1.5px solid ${form.nivel_treino === nivel ? OB_ACCENT : OB_BORDER}`,
                borderRadius: "10px", cursor: "pointer", display: "flex", alignItems: "center", gap: "12px", textAlign: "left",
              }}>
              <span style={{ fontSize: "20px" }}>{icon}</span>
              <div>
                <p style={{ color: form.nivel_treino === nivel ? OB_ACCENT : "white", fontSize: "14px", fontWeight: "600", margin: 0 }}>{nivel}</p>
                <p style={{ color: OB_MUTED, fontSize: "12px", margin: "2px 0 0" }}>{desc}</p>
              </div>
              {form.nivel_treino === nivel && <span style={{ marginLeft: "auto", color: OB_ACCENT }}>✓</span>}
            </button>
          ))}
        </div>
      </div>
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Já treinou antes?</label>
        <div style={{ display: "flex", gap: "8px" }}>
          {["Sim", "Não"].map(op => (
            <OptionBtn key={op} label={op} selected={form.treinou_antes === op} onClick={() => set("treinou_antes", op)} />
          ))}
        </div>
      </div>
      {form.treinou_antes === "Sim" && (
        <div style={{ marginBottom: "16px" }}>
          <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Quanto tempo parado?</label>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            {["Menos de 3 meses", "3 a 6 meses", "6 meses a 1 ano", "Mais de 1 ano"].map(op => (
              <OptionBtn key={op} label={op} selected={form.tempo_parado === op} onClick={() => set("tempo_parado", op)} />
            ))}
          </div>
        </div>
      )}
      <NavBtns onBack={back} onNext={next} canNext={!!form.nivel_treino} />
    </>
  );

  // ─── ETAPA 4 — Rotina ───
  if (step === 4) return wrap(
    <>
      <StepHeader title="Como é sua rotina?" subtitle="Vamos encaixar o treino na sua vida real." />
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Dias disponíveis por semana</label>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {["2 dias", "3 dias", "4 dias", "5 dias", "6 dias"].map(op => (
            <OptionBtn key={op} label={op} selected={form.dias_treino === op} onClick={() => set("dias_treino", op)} />
          ))}
        </div>
      </div>
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Horário preferido</label>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {[["Manhã", "🌅"], ["Tarde", "☀️"], ["Noite", "🌙"], ["Variado", "🔄"]].map(([op, icon]) => (
            <OptionBtn key={op} label={op} icon={icon} selected={form.horario_treino === op} onClick={() => set("horario_treino", op)} />
          ))}
        </div>
      </div>
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Tempo por treino</label>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {["30 min", "45 min", "60 min", "90 min+"].map(op => (
            <OptionBtn key={op} label={op} selected={form.tempo_por_treino === op} onClick={() => set("tempo_por_treino", op)} />
          ))}
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
        <div>
          <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Tipo de trabalho</label>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {["Sentado", "Ativo", "Misto"].map(op => (
              <OptionBtn key={op} label={op} wide selected={form.tipo_trabalho === op} onClick={() => set("tipo_trabalho", op)} />
            ))}
          </div>
        </div>
        <div>
          <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Nível de estresse</label>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {["Baixo", "Médio", "Alto"].map(op => (
              <OptionBtn key={op} label={op} wide selected={form.nivel_estresse === op} onClick={() => set("nivel_estresse", op)} />
            ))}
          </div>
        </div>
      </div>
      <div style={{ marginTop: "16px", marginBottom: "4px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Qualidade do sono</label>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {["Ruim (< 5h)", "Regular (5-6h)", "Bom (6-8h)", "Ótimo (8h+)"].map(op => (
            <OptionBtn key={op} label={op} selected={form.qualidade_sono === op} onClick={() => set("qualidade_sono", op)} />
          ))}
        </div>
      </div>
      <NavBtns onBack={back} onNext={next} canNext={!!form.dias_treino} />
    </>
  );

  // ─── ETAPA 5 — Saúde ───
  if (step === 5) return wrap(
    <>
      <StepHeader title="Saúde e limitações" subtitle="Fundamental para um treino seguro e eficaz." />
      <OBTextarea
        label="Lesões ou restrições físicas"
        name="lesoes"
        value={form.lesoes}
        onChange={v => set("lesoes", v)}
        placeholder="Ex: Dor no joelho, hérnia de disco, tendinite... ou 'Nenhuma'"
      />
      <OBTextarea
        label="Dores frequentes"
        name="dores"
        value={form.dores}
        onChange={v => set("dores", v)}
        placeholder="Ex: Lombar, cervical, ombro... ou 'Nenhuma'"
      />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
        <div>
          <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Usa medicamentos?</label>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {["Não", "Sim"].map(op => (
              <OptionBtn key={op} label={op} wide selected={form.medicamentos === op || (op === "Sim" && form.medicamentos !== "" && form.medicamentos !== "Não")} onClick={() => set("medicamentos", op)} />
            ))}
          </div>
        </div>
        <div>
          <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Prob. hormonais?</label>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {["Não", "Sim"].map(op => (
              <OptionBtn key={op} label={op} wide selected={form.problemas_hormonais === op} onClick={() => set("problemas_hormonais", op)} />
            ))}
          </div>
        </div>
      </div>
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Problemas cardíacos?</label>
        <div style={{ display: "flex", gap: "8px" }}>
          {["Não", "Sim", "Sob acompanhamento médico"].map(op => (
            <OptionBtn key={op} label={op} selected={form.problemas_cardiacos === op} onClick={() => set("problemas_cardiacos", op)} />
          ))}
        </div>
      </div>
      <NavBtns onBack={back} onNext={next} canNext />
    </>
  );

  // ─── ETAPA 6 — Alimentação ───
  if (step === 6) return wrap(
    <>
      <StepHeader title="Como é sua alimentação?" subtitle="A dieta representa 70% do resultado." />
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Refeições por dia</label>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {["2", "3", "4", "5", "6+"].map(op => (
            <OptionBtn key={op} label={op + " refeições"} selected={form.refeicoes_dia === op} onClick={() => set("refeicoes_dia", op)} />
          ))}
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
        <div>
          <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Consome álcool?</label>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {["Não", "Ocasional", "Frequente"].map(op => (
              <OptionBtn key={op} label={op} wide selected={form.consome_alcool === op} onClick={() => set("consome_alcool", op)} />
            ))}
          </div>
        </div>
        <div>
          <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Hidratação</label>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {["Pouco (< 1L)", "Ok (1-2L)", "Boa (2L+)"].map(op => (
              <OptionBtn key={op} label={op} wide selected={form.bebe_agua === op} onClick={() => set("bebe_agua", op)} />
            ))}
          </div>
        </div>
      </div>
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Compulsão alimentar?</label>
        <div style={{ display: "flex", gap: "8px" }}>
          {["Não", "Às vezes", "Frequentemente"].map(op => (
            <OptionBtn key={op} label={op} selected={form.tem_compulsao === op} onClick={() => set("tem_compulsao", op)} />
          ))}
        </div>
      </div>
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Maior dificuldade alimentar</label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
          {["Fome excessiva", "Falta de tempo", "Custo da alimentação", "Não sei o que comer", "Ansiedade", "Comer fora de casa"].map(op => (
            <OptionBtn key={op} label={op} selected={form.dificuldade_alimentar === op} onClick={() => set("dificuldade_alimentar", op)} />
          ))}
        </div>
      </div>
      <OBTextarea label="Descreva sua alimentação atual" name="alimentacao_atual" value={form.alimentacao_atual} onChange={v => set("alimentacao_atual", v)} placeholder="Ex: Café da manhã com pão, almoço no restaurante, jantar leve..." />
      <NavBtns onBack={back} onNext={next} canNext />
    </>
  );

  // ─── ETAPA 7 — Ambiente ───
  if (step === 7) return wrap(
    <>
      <StepHeader title="Onde você vai treinar?" subtitle="Para montar o treino certo com o que você tem." />
      <div style={{ marginBottom: "20px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Local de treino</label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
          {[["Academia", "🏋️"], ["Condomínio", "🏢"], ["Casa", "🏠"], ["Ar livre", "🌳"]].map(([op, icon]) => (
            <OptionBtn key={op} label={op} icon={icon} selected={form.ambiente_treino === op} onClick={() => set("ambiente_treino", op)} />
          ))}
        </div>
      </div>
      <div style={{ marginBottom: "20px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Tem equipamentos em casa?</label>
        <div style={{ display: "flex", gap: "8px" }}>
          {["Não", "Alguns (halteres, elástico)", "Sim, equipamento completo"].map(op => (
            <OptionBtn key={op} label={op} selected={form.tem_equipamentos === op} onClick={() => set("tem_equipamentos", op)} />
          ))}
        </div>
      </div>
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Tem acesso a cardio? (esteira, bike...)</label>
        <div style={{ display: "flex", gap: "8px" }}>
          {["Sim", "Não", "Faço cardio ao ar livre"].map(op => (
            <OptionBtn key={op} label={op} selected={form.cardio_disponivel === op} onClick={() => set("cardio_disponivel", op)} />
          ))}
        </div>
      </div>
      <NavBtns onBack={back} onNext={next} canNext={!!form.ambiente_treino} />
    </>
  );

  // ─── ETAPA 8 — Foto ───
  if (step === 8) return wrap(
    <>
      <StepHeader title="Foto inicial" subtitle="Opcional. Ajuda a personalizar e comparar sua evolução." />
      <div style={{ background: OB_CARD, border: `1.5px dashed ${OB_BORDER}`, borderRadius: "12px", padding: "32px 24px", textAlign: "center", marginBottom: "20px" }}>
        <span style={{ fontSize: "36px", display: "block", marginBottom: "12px" }}>📸</span>
        <p style={{ color: "#9ca3af", fontSize: "14px", marginBottom: "8px" }}>Upload de foto disponível em breve</p>
        <p style={{ color: "#4b5563", fontSize: "12px", lineHeight: "1.5" }}>
          Você poderá adicionar fotos de frente, lado e costas<br />no app após receber seu plano.
        </p>
      </div>
      <div style={{ background: `${OB_ACCENT}10`, border: `1px solid ${OB_ACCENT}30`, borderRadius: "10px", padding: "14px 16px" }}>
        <p style={{ color: OB_ACCENT, fontSize: "12px", fontWeight: "600", marginBottom: "4px" }}>Por que fotos ajudam?</p>
        <p style={{ color: "#9ca3af", fontSize: "12px", lineHeight: "1.5" }}>
          As fotos permitem comparar seu progresso real entre avaliações e alimentam a análise de composição corporal.
        </p>
      </div>
      <NavBtns onBack={back} onNext={next} canNext />
    </>
  );

  // ─── ETAPA 9 — Comportamento ───
  if (step === 9) return wrap(
    <>
      <StepHeader title="Últimas perguntas" subtitle="Essas respostas alimentam nosso sistema de retenção e acompanhamento." />
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: OB_MUTED, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>O que mais te impede de evoluir?</label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "10px" }}>
          {["Falta de tempo", "Falta de motivação", "Alimentação difícil", "Lesão ou dor", "Trabalho pesado", "Vida social"].map(op => (
            <OptionBtn key={op} label={op} selected={form.impedimento_principal === op} onClick={() => set("impedimento_principal", op)} />
          ))}
        </div>
      </div>
      <OBTextarea
        label="O que te faria desistir?"
        name="motivo_desistencia"
        value={form.motivo_desistencia}
        onChange={v => set("motivo_desistencia", v)}
        placeholder="Seja honesto. Isso nos ajuda a evitar que isso aconteça."
        hint="Sua resposta é confidencial e usada só para personalizar seu acompanhamento."
      />
      <OBTextarea
        label="O que você espera da Sotel Fit Core?"
        name="expectativa"
        value={form.expectativa}
        onChange={v => set("expectativa", v)}
        placeholder="Ex: Emagrecer 10kg, ganhar massa, ter saúde, energia no dia a dia..."
      />
      <NavBtns
        onBack={back}
        onNext={handleSubmit}
        nextLabel="Enviar cadastro ✓"
        loading={loading}
        canNext={!!form.expectativa || !!form.impedimento_principal}
      />
    </>
  );

  return null;
}

/* ─────────────────────────────────────────────
   RESTO DO APP (sem alterações)
───────────────────────────────────────────── */

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

function OnboardingModal({ onboarding, onClose, apiKey, phone }: { onboarding: Onboarding | null; onClose: () => void; apiKey: string; phone: string }) {
  const [aiAnalysis, setAiAnalysis] = useState<any>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");

  const loadAiAnalysis = async () => {
    setAiLoading(true);
    setAiError("");
    try {
      const encoded = encodeURIComponent(phone);
      const res = await fetch(API + `/ai-admin/onboarding-analysis/${encoded}`, {
        headers: { "x-api-key": apiKey }
      });
      if (!res.ok) throw new Error("Erro ao gerar análise");
      const data = await res.json();
      setAiAnalysis(data.analysis);
    } catch {
      setAiError("Erro ao gerar análise. Tente novamente.");
    } finally {
      setAiLoading(false);
    }
  };

  const riskColor = (val: string) => {
    if (!val) return "#64748b";
    const v = val.toLowerCase();
    if (v === "alto" || v === "baixa") return "#ef4444";
    if (v === "medio" || v === "média" || v === "media") return "#f59e0b";
    return "#22c55e";
  };

  const field = (label: string, value: string | null) => value ? (
    <div style={{ marginBottom: "12px" }}>
      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "2px" }}>{label}</p>
      <p style={{ color: "white", fontSize: "14px" }}>{value}</p>
    </div>
  ) : null;

  const parseExtra = (obs: string | null) => {
    if (!obs) return null;
    try { return JSON.parse(obs); } catch { return null; }
  };
  const extra = onboarding ? parseExtra(onboarding.observacoes) : null;

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "20px" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{ background: "#1e293b", borderRadius: "16px", maxWidth: "700px", width: "100%", border: "1px solid #334155", maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "24px 28px", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ color: "white", fontSize: "18px", fontWeight: "700" }}>
              {onboarding ? `📋 Onboarding — ${onboarding.nome || "Sem nome"}` : "📋 Onboarding não enviado"}
            </h2>
            {onboarding && <p style={{ color: "#64748b", fontSize: "12px", marginTop: "4px" }}>Enviado em {new Date(onboarding.created_at).toLocaleDateString("pt-BR")}</p>}
          </div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            {onboarding && (
              <button onClick={loadAiAnalysis} disabled={aiLoading}
                style={{ background: aiAnalysis ? "#14532d" : "#7c3aed", color: "white", border: "none", padding: "8px 14px", borderRadius: "8px", cursor: "pointer", fontSize: "12px", fontWeight: "600" }}>
                {aiLoading ? "Analisando..." : aiAnalysis ? "✓ IA Analisada" : "🤖 Analisar com IA"}
              </button>
            )}
            <button onClick={onClose} style={{ background: "#334155", color: "white", border: "none", padding: "8px 12px", borderRadius: "8px", cursor: "pointer", fontSize: "16px" }}>×</button>
          </div>
        </div>
        <div style={{ padding: "24px 28px", overflowY: "auto" }}>
          {!onboarding ? (
            <div style={{ textAlign: "center", padding: "32px 0" }}>
              <p style={{ color: "#64748b" }}>Este lead ainda não preencheu o formulário de onboarding.</p>
            </div>
          ) : (
            <>
              <h3 style={{ color: "#3b82f6", fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "14px" }}>Identidade</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px", marginBottom: "4px" }}>
                {field("Nome", onboarding.nome)}
                {field("Email", onboarding.email)}
                {field("Telefone", onboarding.telefone)}
                {field("Idade", onboarding.idade ? onboarding.idade + " anos" : null)}
                {field("Peso", onboarding.peso ? onboarding.peso + " kg" : null)}
                {field("Altura", onboarding.altura ? onboarding.altura + " cm" : null)}
                {extra && field("Sexo", extra.sexo)}
                {extra && field("Cidade", extra.cidade)}
              </div>
              <div style={{ borderTop: "1px solid #334155", margin: "16px 0" }} />
              <h3 style={{ color: "#3b82f6", fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "14px" }}>Objetivo e Experiência</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
                {field("Objetivo", onboarding.objetivo)}
                {field("Nível", onboarding.nivel_treino)}
                {field("Dias de treino", onboarding.dias_treino)}
                {field("Horário", onboarding.horario_treino)}
                {extra && field("Tempo por treino", extra.tempo_por_treino)}
                {extra && field("Treinou antes?", extra.treinou_antes)}
              </div>
              <div style={{ borderTop: "1px solid #334155", margin: "16px 0" }} />
              <h3 style={{ color: "#3b82f6", fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "14px" }}>Rotina e Saúde</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
                {extra && field("Tipo de trabalho", extra.tipo_trabalho)}
                {extra && field("Nível de estresse", extra.nivel_estresse)}
                {extra && field("Qualidade do sono", extra.qualidade_sono)}
                {extra && field("Prob. hormonais", extra.problemas_hormonais)}
                {extra && field("Prob. cardíacos", extra.problemas_cardiacos)}
                {extra && field("Medicamentos", extra.medicamentos)}
              </div>
              {field("Lesões / restrições", onboarding.lesoes)}
              {extra && field("Dores frequentes", extra.dores)}
              <div style={{ borderTop: "1px solid #334155", margin: "16px 0" }} />
              <h3 style={{ color: "#3b82f6", fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "14px" }}>Alimentação</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
                {extra && field("Refeições/dia", extra.refeicoes_dia)}
                {extra && field("Álcool", extra.consome_alcool)}
                {extra && field("Hidratação", extra.bebe_agua)}
                {extra && field("Compulsão", extra.tem_compulsao)}
                {extra && field("Dificuldade alimentar", extra.dificuldade_alimentar)}
              </div>
              {field("Alimentação atual", onboarding.alimentacao_atual)}
              <div style={{ borderTop: "1px solid #334155", margin: "16px 0" }} />
              <h3 style={{ color: "#3b82f6", fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "14px" }}>Ambiente e Comportamento</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
                {extra && field("Ambiente de treino", extra.ambiente_treino)}
                {extra && field("Tem equipamentos", extra.tem_equipamentos)}
                {extra && field("Cardio disponível", extra.cardio_disponivel)}
                {extra && field("Principal impedimento", extra.impedimento_principal)}
              </div>
              {extra && field("O que te faria desistir?", extra.motivo_desistencia)}
              {extra && field("Expectativa", extra.expectativa)}
              {field("Meta principal", onboarding.meta_principal)}
            </>
          )}
          {/* AI ANALYSIS SECTION */}
          {aiError && (
            <div style={{ background: "#7f1d1d", border: "1px solid #ef4444", borderRadius: "8px", padding: "10px 14px", marginTop: "16px", color: "white", fontSize: "13px" }}>{aiError}</div>
          )}
          {aiAnalysis && (
            <div style={{ marginTop: "24px" }}>
              <div style={{ borderTop: "1px solid #334155", marginBottom: "20px" }} />
              <h3 style={{ color: "#7c3aed", fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "14px" }}>🤖 Análise IA Operacional</h3>

              {/* Resumo */}
              <div style={{ background: "#0f172a", border: "1px solid #334155", borderRadius: "10px", padding: "14px 16px", marginBottom: "14px" }}>
                <p style={{ color: "#94a3b8", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "8px" }}>Resumo Operacional</p>
                <p style={{ color: "#e2e8f0", fontSize: "13px", lineHeight: "1.6" }}>{aiAnalysis.resumo_operacional}</p>
              </div>

              {/* Classificação */}
              {aiAnalysis.classificacao && (
                <div style={{ background: "#0f172a", border: "1px solid #334155", borderRadius: "10px", padding: "14px 16px", marginBottom: "14px" }}>
                  <p style={{ color: "#94a3b8", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>Classificação</p>
                  <p style={{ color: "white", fontSize: "14px", fontWeight: "600", marginBottom: "10px" }}>{aiAnalysis.classificacao.perfil}</p>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", marginBottom: "8px" }}>
                    {[
                      ["Comprometimento", aiAnalysis.classificacao.comprometimento],
                      ["Risco abandono", aiAnalysis.classificacao.risco_abandono],
                      ["Aderência provável", aiAnalysis.classificacao.aderencia_provavel],
                    ].map(([label, val]) => (
                      <div key={label} style={{ background: "#1e293b", borderRadius: "8px", padding: "8px 10px", textAlign: "center" }}>
                        <p style={{ color: "#64748b", fontSize: "10px", marginBottom: "4px" }}>{label}</p>
                        <p style={{ color: riskColor(val as string), fontSize: "13px", fontWeight: "700", textTransform: "capitalize" }}>{val || "–"}</p>
                      </div>
                    ))}
                  </div>
                  {aiAnalysis.classificacao.observacao && (
                    <p style={{ color: "#64748b", fontSize: "12px", marginTop: "6px" }}>{aiAnalysis.classificacao.observacao}</p>
                  )}
                </div>
              )}

              {/* Treino + Dieta */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "14px" }}>
                {aiAnalysis.sugestao_treino && (
                  <div style={{ background: "#0f172a", border: "1px solid #334155", borderRadius: "10px", padding: "14px 16px" }}>
                    <p style={{ color: "#3b82f6", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>💪 Treino Base</p>
                    <p style={{ color: "white", fontSize: "13px", fontWeight: "600", marginBottom: "4px" }}>{aiAnalysis.sugestao_treino.divisao}</p>
                    <p style={{ color: "#94a3b8", fontSize: "12px", marginBottom: "4px" }}>{aiAnalysis.sugestao_treino.frequencia}</p>
                    <p style={{ color: "#94a3b8", fontSize: "12px", marginBottom: "4px" }}>Intensidade: {aiAnalysis.sugestao_treino.intensidade}</p>
                    <p style={{ color: "#64748b", fontSize: "12px", marginTop: "6px" }}>{aiAnalysis.sugestao_treino.observacoes}</p>
                  </div>
                )}
                {aiAnalysis.sugestao_dieta && (
                  <div style={{ background: "#0f172a", border: "1px solid #334155", borderRadius: "10px", padding: "14px 16px" }}>
                    <p style={{ color: "#22c55e", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>🥗 Dieta Base</p>
                    <p style={{ color: "white", fontSize: "13px", fontWeight: "600", marginBottom: "4px" }}>{aiAnalysis.sugestao_dieta.estrategia}</p>
                    <p style={{ color: "#94a3b8", fontSize: "12px", marginBottom: "4px" }}>{aiAnalysis.sugestao_dieta.distribuicao}</p>
                    <p style={{ color: "#94a3b8", fontSize: "12px" }}>{aiAnalysis.sugestao_dieta.foco}</p>
                    <p style={{ color: "#64748b", fontSize: "12px", marginTop: "6px" }}>{aiAnalysis.sugestao_dieta.observacoes}</p>
                  </div>
                )}
              </div>

              {/* Insights */}
              {aiAnalysis.insights && aiAnalysis.insights.length > 0 && (
                <div style={{ background: "#0f172a", border: "1px solid #334155", borderRadius: "10px", padding: "14px 16px" }}>
                  <p style={{ color: "#f59e0b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "10px" }}>⚡ Insights Operacionais</p>
                  {aiAnalysis.insights.map((insight: string, i: number) => (
                    <div key={i} style={{ display: "flex", gap: "8px", alignItems: "flex-start", marginBottom: "6px" }}>
                      <span style={{ color: "#f59e0b", fontSize: "12px", marginTop: "1px" }}>•</span>
                      <p style={{ color: "#cbd5e1", fontSize: "13px", lineHeight: "1.4" }}>{insight}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
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
              <p style={{ color: "#64748b" }}>Nenhum check-in registrado ainda.</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {checkins.map((ci, i) => (
                <div key={i} style={{ background: "#0f172a", borderRadius: "8px", padding: "16px", border: "1px solid #334155" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "12px" }}>
                    <div><p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Treinou</p><p style={{ color: "white", fontSize: "14px" }}>{ci.treinou || "–"}</p></div>
                    <div><p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Seguiu dieta</p><p style={{ color: "white", fontSize: "14px" }}>{ci.seguiu_dieta || "–"}</p></div>
                    <div><p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Peso</p><p style={{ color: "white", fontSize: "14px" }}>{ci.peso ? ci.peso + " kg" : "–"}</p></div>
                    <div><p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Data</p><p style={{ color: "white", fontSize: "14px" }}>{new Date(ci.created_at).toLocaleDateString("pt-BR")}</p></div>
                  </div>
                  {ci.dificuldade && <div style={{ marginBottom: "8px" }}><p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Dificuldade</p><p style={{ color: "#fbbf24", fontSize: "13px" }}>{ci.dificuldade}</p></div>}
                  {ci.observacoes && <div><p style={{ color: "#64748b", fontSize: "11px", fontWeight: "600", textTransform: "uppercase", marginBottom: "4px" }}>Observações</p><p style={{ color: "#e5e7eb", fontSize: "13px" }}>{ci.observacoes}</p></div>}
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
      const res = await fetch(API + `/admin/clients/${client.id}/save-plan`, { method: "POST", headers, body: JSON.stringify({ content: treino }) });
      if (res.ok) setMsg({ text: "Treino salvo!", type: "success" });
      else setMsg({ text: "Erro ao salvar treino.", type: "error" });
    } catch { setMsg({ text: "Erro de conexão.", type: "error" }); } finally { setLoading(false); }
  };

  const saveDiet = async () => {
    if (!dieta.trim()) { setMsg({ text: "Preencha o plano alimentar.", type: "error" }); return; }
    setLoading(true);
    try {
      const res = await fetch(API + `/admin/clients/${client.id}/save-diet`, { method: "POST", headers, body: JSON.stringify({ content: dieta }) });
      if (res.ok) setMsg({ text: "Dieta salva!", type: "success" });
      else setMsg({ text: "Erro ao salvar dieta.", type: "error" });
    } catch { setMsg({ text: "Erro de conexão.", type: "error" }); } finally { setLoading(false); }
  };

  const saveAll = async () => {
    setLoading(true); setMsg(null);
    try {
      const [r1, r2] = await Promise.all([
        fetch(API + `/admin/clients/${client.id}/save-plan`, { method: "POST", headers, body: JSON.stringify({ content: treino }) }),
        fetch(API + `/admin/clients/${client.id}/save-diet`, { method: "POST", headers, body: JSON.stringify({ content: dieta }) }),
      ]);
      if (r1.ok && r2.ok) setMsg({ text: "Treino e dieta salvos!", type: "success" });
      else setMsg({ text: "Erro ao salvar.", type: "error" });
    } catch { setMsg({ text: "Erro de conexão.", type: "error" }); } finally { setLoading(false); }
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
            <div style={{ background: msg.type === "success" ? "#14532d" : "#7f1d1d", border: `1px solid ${msg.type === "success" ? "#22c55e" : "#ef4444"}`, borderRadius: "8px", padding: "10px 14px", color: "white", fontSize: "14px" }}>{msg.text}</div>
          )}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <label style={{ color: "#94a3b8", fontSize: "13px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em" }}>💪 Plano de Treino</label>
              <button onClick={savePlan} disabled={loading} style={{ background: "#1d4ed8", color: "white", border: "none", padding: "6px 14px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600" }}>Salvar treino</button>
            </div>
            <textarea value={treino} onChange={(e) => setTreino(e.target.value)} placeholder={"SEGUNDA - Peito e Tríceps\nSupino reto: 4x10\n\nTERÇA - Costas e Bíceps\nPuxada: 4x10..."}
              style={{ width: "100%", height: "200px", background: "#0f172a", border: "1px solid #334155", borderRadius: "8px", padding: "12px", color: "white", fontSize: "13px", resize: "vertical", boxSizing: "border-box", fontFamily: "monospace", lineHeight: "1.5" }} />
          </div>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <label style={{ color: "#94a3b8", fontSize: "13px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em" }}>🥗 Plano Alimentar</label>
              <button onClick={saveDiet} disabled={loading} style={{ background: "#15803d", color: "white", border: "none", padding: "6px 14px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600" }}>Salvar dieta</button>
            </div>
            <textarea value={dieta} onChange={(e) => setDieta(e.target.value)} placeholder={"CAFÉ DA MANHÃ (7h)\n3 ovos + 2 pães integrais\n\nALMOÇO (12h)\n150g frango + arroz + legumes..."}
              style={{ width: "100%", height: "200px", background: "#0f172a", border: "1px solid #334155", borderRadius: "8px", padding: "12px", color: "white", fontSize: "13px", resize: "vertical", boxSizing: "border-box", fontFamily: "monospace", lineHeight: "1.5" }} />
          </div>
          <button onClick={saveAll} disabled={loading} style={{ width: "100%", padding: "14px", background: "#7c3aed", color: "white", border: "none", borderRadius: "8px", fontSize: "15px", fontWeight: "700", cursor: "pointer" }}>
            {loading ? "Salvando..." : "💾 Salvar treino + dieta"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Login() {
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault(); setLoading(true); setError("");
    try {
      const formatted = normalize_phone(phone);
      const res = await fetch(API + `/clients/by-phone/${encodeURIComponent(formatted)}`);
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem("clientPhone", formatted);
        localStorage.setItem("clientData", JSON.stringify(data));
        navigate("/dashboard");
      } else { setError("Número não encontrado. Verifique se completou o cadastro."); }
    } catch { setError("Erro ao conectar com o servidor."); } finally { setLoading(false); }
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
            <p style={{ color: "#6b7280", fontSize: "14px" }}>Responda como foi sua semana.</p>
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
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientData.id, treinou: form.treinou, seguiu_dieta: form.seguiu_dieta, peso: form.peso ? parseFloat(form.peso) : null, energia: null, dificuldade: form.dificuldade, observacoes: form.observacoes }),
      });
    } catch (e) { console.error(e); }
    setEnviado(true);
  };

  if (enviado) return (
    <div style={{ minHeight: "100vh", background: "#f0f4f8", fontFamily: "Arial" }}>
      <Navbar name={firstName} onLogout={logout} />
      <div style={{ maxWidth: "600px", margin: "80px auto", background: "white", borderRadius: "12px", padding: "40px", textAlign: "center", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
        <div style={{ fontSize: "64px", marginBottom: "16px" }}>✅</div>
        <h2 style={{ fontSize: "24px", fontWeight: "700", marginBottom: "8px" }}>Check-in Enviado!</h2>
        <p style={{ color: "#6b7280", marginBottom: "24px" }}>Seu treinador vai analisar em breve.</p>
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
                  <input type="radio" name="treinou" value={op} onChange={e => setForm({ ...form, treinou: e.target.value })} required />{op}
                </label>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Seguiu a alimentação?</label>
            <div style={{ display: "flex", gap: "12px" }}>
              {["Sim", "Parcialmente", "Não"].map(op => (
                <label key={op} style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                  <input type="radio" name="seguiu_dieta" value={op} onChange={e => setForm({ ...form, seguiu_dieta: e.target.value })} required />{op}
                </label>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Peso atual (kg)</label>
            <input type="number" step="0.1" placeholder="Ex: 70.5" value={form.peso} onChange={e => setForm({ ...form, peso: e.target.value })}
              style={{ width: "100%", padding: "10px", border: "1px solid #d1d5db", borderRadius: "8px", boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Teve alguma dificuldade?</label>
            <input type="text" placeholder="Ex: Fome à noite, dor no joelho..." value={form.dificuldade} onChange={e => setForm({ ...form, dificuldade: e.target.value })}
              style={{ width: "100%", padding: "10px", border: "1px solid #d1d5db", borderRadius: "8px", boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: "24px" }}>
            <label style={{ display: "block", fontWeight: "600", marginBottom: "8px" }}>Observações gerais</label>
            <textarea placeholder="Como você está se sentindo?" value={form.observacoes} onChange={e => setForm({ ...form, observacoes: e.target.value })}
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
    e.preventDefault(); setLoading(true); setError("");
    try {
      const res = await fetch(API + "/admin/leads", { headers: { "x-api-key": apiKey } });
      if (res.ok) { localStorage.setItem("adminKey", apiKey); navigate("/admin/dashboard"); }
      else setError("Chave inválida.");
    } catch { setError("Erro ao conectar."); } finally { setLoading(false); }
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
  const [modalPhone, setModalPhone] = useState<string>("");
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
      setLeads(Array.isArray(await leadsRes.json()) ? await (await fetch(API + "/admin/leads", { headers })).json() : []);
      setClients(Array.isArray(await clientsRes.json()) ? await (await fetch(API + "/admin/clients", { headers })).json() : []);
    } catch { setMsg({ text: "Erro ao carregar dados.", type: "error" }); } finally { setLoading(false); }
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [r1, r2] = await Promise.all([
          fetch(API + "/admin/leads", { headers }),
          fetch(API + "/admin/clients", { headers }),
        ]);
        const d1 = await r1.json(); const d2 = await r2.json();
        setLeads(Array.isArray(d1) ? d1 : []);
        setClients(Array.isArray(d2) ? d2 : []);
      } catch { setMsg({ text: "Erro ao carregar.", type: "error" }); } finally { setLoading(false); }
    };
    load();
  }, []);

  const viewOnboarding = async (phone: string) => {
    setModalState("loading"); setModalData(null); setModalPhone(phone);
    try {
      const res = await fetch(API + `/admin/onboardings/by-phone/${encodeURIComponent(phone)}`, { headers });
      setModalData(await res.json() || null);
    } catch { setModalData(null); } finally { setModalState("open"); }
  };

  const activateLead = async (phone: string) => {
    setActionLoading(phone + "_activate");
    try {
      const res = await fetch(API + "/admin/twilio/activate-lead", { method: "POST", headers, body: JSON.stringify({ phone }) });
      const data = await res.json();
      setMsg({ text: data.message || "Lead ativado!", type: "success" });
    } catch { setMsg({ text: "Erro ao ativar lead.", type: "error" }); } finally { setActionLoading(null); }
  };

  const releasePlan = async (phone: string) => {
    setActionLoading(phone + "_release");
    try {
      const res = await fetch(API + "/admin/twilio/release-plan", { method: "POST", headers, body: JSON.stringify({ phone }) });
      const data = await res.json();
      setMsg({ text: data.message || "Plano liberado!", type: "success" });
    } catch { setMsg({ text: "Erro ao liberar.", type: "error" }); } finally { setActionLoading(null); }
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
      {modalState === "open" && <OnboardingModal onboarding={modalData} onClose={() => setModalState("closed")} apiKey={apiKey} phone={modalPhone} />}
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
                        <button onClick={() => setPlanModal(client)} style={{ background: "#7c3aed", color: "white", border: "none", padding: "8px 16px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600" }}>🏋️ Plano</button>
                        <button onClick={() => setCheckinModal(client)} style={{ background: "#1d4ed8", color: "white", border: "none", padding: "8px 16px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600" }}>📋 Check-ins</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

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
                          <button onClick={() => viewOnboarding(lead.phone)} style={{ background: "#1e3a5f", color: "#93c5fd", border: "1px solid #1d4ed8", padding: "6px 10px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600", whiteSpace: "nowrap" }}>📋 Onboarding</button>
                          {!lead.onboarding_link_sent && (
                            <button onClick={() => activateLead(lead.phone)} disabled={actionLoading === lead.phone + "_activate"} style={{ background: "#1d4ed8", color: "white", border: "none", padding: "6px 10px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600", whiteSpace: "nowrap" }}>
                              {actionLoading === lead.phone + "_activate" ? "..." : "📲 Ativar"}
                            </button>
                          )}
                          {(lead.status === "active_client" || lead.status === "onboarding_pending" || lead.status === "onboarding_completed") && (
                            <button onClick={() => releasePlan(lead.phone)} disabled={actionLoading === lead.phone + "_release"} style={{ background: "#15803d", color: "white", border: "none", padding: "6px 10px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600", whiteSpace: "nowrap" }}>
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
