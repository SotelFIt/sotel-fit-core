/*
 * LIB-004 - Biblioteca de Exercicios V2 (Painel Administrativo).
 *
 * Frontend-only: consome EXCLUSIVAMENTE a API da LIB-003 ja mergeada:
 *   - GET   /exercises            (admin via x-api-key ve ativos + inativos)
 *   - GET   /exercises/{slug}
 *   - POST  /admin/exercises
 *   - PATCH /admin/exercises/{slug}
 *
 * Autenticacao admin: mesma convencao do painel existente (localStorage.adminKey
 * enviado como header x-api-key). Nenhuma alteracao de backend/auth/contrato.
 */
import { useState, useEffect, useCallback } from "react";
import { Navigate, useNavigate } from "react-router-dom";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

const LEVELS = ["iniciante", "intermediario", "avancado"] as const;
type Level = (typeof LEVELS)[number];

interface Media {
  type: string;
  url: string;
  alt?: string | null;
}

interface Exercise {
  id: number;
  slug: string;
  name: string;
  primary_muscle: string;
  secondary_muscles: string[];
  equipment: string;
  level: Level;
  instructions: string | null;
  common_errors: string[];
  cautions: string[];
  approved_substitutions: string[];
  media: Media[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Filters {
  q: string;
  primary_muscle: string;
  equipment: string;
  level: string;
  is_active: string; // "", "true", "false"
}

const EMPTY_FILTERS: Filters = { q: "", primary_muscle: "", equipment: "", level: "", is_active: "" };

// ---- paleta (mesmo tema escuro do painel admin) ----
const C = {
  bg: "#0f172a",
  card: "#1e293b",
  border: "#334155",
  muted: "#94a3b8",
  faint: "#64748b",
  accent: "#2563eb",
  green: "#22c55e",
  red: "#ef4444",
  amber: "#f59e0b",
};

const PAGE_SIZE = 10;

// ---- helpers ----
const csvToArray = (s: string): string[] =>
  s.split(",").map((x) => x.trim()).filter(Boolean);
const arrayToCsv = (a: string[]): string => a.join(", ");

interface FormState {
  slug: string;
  name: string;
  primary_muscle: string;
  equipment: string;
  level: Level;
  secondary_muscles: string;
  instructions: string;
  common_errors: string;
  cautions: string;
  approved_substitutions: string[];
  media: Media[];
  is_active: boolean;
}

const emptyForm = (): FormState => ({
  slug: "",
  name: "",
  primary_muscle: "",
  equipment: "",
  level: "iniciante",
  secondary_muscles: "",
  instructions: "",
  common_errors: "",
  cautions: "",
  approved_substitutions: [],
  media: [],
  is_active: true,
});

const formFromExercise = (ex: Exercise): FormState => ({
  slug: ex.slug,
  name: ex.name,
  primary_muscle: ex.primary_muscle,
  equipment: ex.equipment,
  level: ex.level,
  secondary_muscles: arrayToCsv(ex.secondary_muscles),
  instructions: ex.instructions ?? "",
  common_errors: arrayToCsv(ex.common_errors),
  cautions: arrayToCsv(ex.cautions),
  approved_substitutions: [...ex.approved_substitutions],
  media: ex.media.map((m) => ({ type: m.type, url: m.url, alt: m.alt ?? "" })),
  is_active: ex.is_active,
});

// estilos reutilizaveis
const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "10px 12px",
  background: C.bg,
  border: `1px solid ${C.border}`,
  borderRadius: "8px",
  fontSize: "14px",
  color: "white",
  boxSizing: "border-box",
};
const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "12px",
  fontWeight: 600,
  color: C.muted,
  marginBottom: "6px",
};
const btn = (bg: string): React.CSSProperties => ({
  background: bg,
  color: "white",
  border: "none",
  padding: "9px 16px",
  borderRadius: "8px",
  cursor: "pointer",
  fontSize: "13px",
  fontWeight: 600,
});

export default function ExerciseLibrary() {
  const navigate = useNavigate();
  const adminKey = localStorage.getItem("adminKey");

  const [items, setItems] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [draft, setDraft] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);

  const [formOpen, setFormOpen] = useState(false);
  const [editingSlug, setEditingSlug] = useState<string | null>(null);
  const [detail, setDetail] = useState<Exercise | null>(null);

  const headers: Record<string, string> = {
    "x-api-key": adminKey || "",
    "Content-Type": "application/json",
  };

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (applied.q) params.set("q", applied.q);
      if (applied.primary_muscle) params.set("primary_muscle", applied.primary_muscle);
      if (applied.equipment) params.set("equipment", applied.equipment);
      if (applied.level) params.set("level", applied.level);
      if (applied.is_active) params.set("is_active", applied.is_active);
      const qs = params.toString();
      const res = await fetch(`${API}/exercises${qs ? "?" + qs : ""}`, { headers });
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      setItems(Array.isArray(data) ? data : []);
      setPage(1);
    } catch {
      setMsg({ text: "Erro ao carregar exercicios.", type: "error" });
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applied]);

  useEffect(() => {
    // Busca de dados na montagem e quando os filtros aplicados mudam: sincroniza
    // com um sistema externo (a API), uso legitimo de efeito. O setState interno
    // (loading/itens) e intencional, dai o disable pontual da regra.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (adminKey) fetchList();
  }, [adminKey, fetchList]);

  if (!adminKey) return <Navigate to="/admin" />;

  const applySearch = () => setApplied(draft);
  const clearFilters = () => {
    setDraft(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
  };

  const openCreate = () => {
    setEditingSlug(null);
    setFormOpen(true);
  };
  const openEdit = (ex: Exercise) => {
    setEditingSlug(ex.slug);
    setFormOpen(true);
  };

  const toggleActive = async (ex: Exercise) => {
    try {
      const res = await fetch(`${API}/admin/exercises/${encodeURIComponent(ex.slug)}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ is_active: !ex.is_active }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || "Falha ao alterar status");
      }
      setMsg({
        text: `Exercicio ${ex.is_active ? "desativado" : "ativado"}: ${ex.slug}`,
        type: "success",
      });
      fetchList();
    } catch (e) {
      setMsg({ text: (e as Error).message, type: "error" });
    }
  };

  // filtragem/paginacao client-side (a API nao pagina)
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageItems = items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const activeCount = items.filter((e) => e.is_active).length;

  return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: "Arial", color: "white" }}>
      <nav
        style={{
          background: C.card,
          borderBottom: `1px solid ${C.border}`,
          padding: "16px 32px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "20px" }}>🏋️</span>
          <h1 style={{ fontSize: "18px", fontWeight: 700 }}>Biblioteca de Exercicios</h1>
        </div>
        <div style={{ display: "flex", gap: "10px" }}>
          <button onClick={() => navigate("/admin/dashboard")} style={{ ...btn("transparent"), border: `1px solid ${C.border}`, color: C.muted }}>
            ← Painel
          </button>
          <button onClick={openCreate} style={btn(C.accent)}>+ Novo exercicio</button>
        </div>
      </nav>

      <main style={{ maxWidth: "1100px", margin: "0 auto", padding: "24px 32px" }}>
        {msg && (
          <div
            style={{
              padding: "12px 16px",
              borderRadius: "8px",
              marginBottom: "16px",
              background: msg.type === "success" ? "#14532d" : "#7f1d1d",
              color: "white",
              fontSize: "14px",
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span>{msg.text}</span>
            <span style={{ cursor: "pointer" }} onClick={() => setMsg(null)}>×</span>
          </div>
        )}

        {/* filtros */}
        <div
          style={{
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: "12px",
            padding: "16px",
            marginBottom: "16px",
            display: "grid",
            gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr auto",
            gap: "10px",
            alignItems: "end",
          }}
        >
          <div>
            <label style={labelStyle}>Busca (nome ou slug)</label>
            <input
              style={inputStyle}
              value={draft.q}
              placeholder="ex: supino"
              onChange={(e) => setDraft({ ...draft, q: e.target.value })}
              onKeyDown={(e) => { if (e.key === "Enter") applySearch(); }}
            />
          </div>
          <div>
            <label style={labelStyle}>Grupo muscular</label>
            <input
              style={inputStyle}
              value={draft.primary_muscle}
              placeholder="Peito"
              onChange={(e) => setDraft({ ...draft, primary_muscle: e.target.value })}
              onKeyDown={(e) => { if (e.key === "Enter") applySearch(); }}
            />
          </div>
          <div>
            <label style={labelStyle}>Equipamento</label>
            <input
              style={inputStyle}
              value={draft.equipment}
              placeholder="Barra"
              onChange={(e) => setDraft({ ...draft, equipment: e.target.value })}
              onKeyDown={(e) => { if (e.key === "Enter") applySearch(); }}
            />
          </div>
          <div>
            <label style={labelStyle}>Nivel</label>
            <select style={inputStyle} value={draft.level} onChange={(e) => setDraft({ ...draft, level: e.target.value })}>
              <option value="">Todos</option>
              {LEVELS.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Status</label>
            <select style={inputStyle} value={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.value })}>
              <option value="">Todos</option>
              <option value="true">Ativos</option>
              <option value="false">Inativos</option>
            </select>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button onClick={applySearch} style={btn(C.accent)}>Filtrar</button>
            <button onClick={clearFilters} style={{ ...btn("transparent"), border: `1px solid ${C.border}`, color: C.muted }}>
              Limpar
            </button>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
          <span style={{ color: C.faint, fontSize: "13px" }}>
            {total} exercicio(s) · {activeCount} ativo(s)
          </span>
        </div>

        {/* tabela */}
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: "12px", overflow: "hidden" }}>
          {loading ? (
            <div style={{ padding: "40px", textAlign: "center", color: C.faint }}>Carregando...</div>
          ) : total === 0 ? (
            <div style={{ padding: "40px", textAlign: "center", color: C.faint }}>Nenhum exercicio encontrado.</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
                <thead>
                  <tr style={{ background: "#0b1220", color: C.muted, textAlign: "left" }}>
                    <th style={{ padding: "12px 16px", fontWeight: 600 }}>Nome</th>
                    <th style={{ padding: "12px 16px", fontWeight: 600 }}>Slug</th>
                    <th style={{ padding: "12px 16px", fontWeight: 600 }}>Grupo muscular</th>
                    <th style={{ padding: "12px 16px", fontWeight: 600 }}>Equipamento</th>
                    <th style={{ padding: "12px 16px", fontWeight: 600 }}>Ativo</th>
                    <th style={{ padding: "12px 16px", fontWeight: 600, textAlign: "right" }}>Acoes</th>
                  </tr>
                </thead>
                <tbody>
                  {pageItems.map((ex) => (
                    <tr key={ex.id} style={{ borderTop: `1px solid ${C.border}` }}>
                      <td style={{ padding: "12px 16px" }}>{ex.name}</td>
                      <td style={{ padding: "12px 16px", color: C.faint, fontFamily: "monospace" }}>{ex.slug}</td>
                      <td style={{ padding: "12px 16px" }}>{ex.primary_muscle}</td>
                      <td style={{ padding: "12px 16px" }}>{ex.equipment}</td>
                      <td style={{ padding: "12px 16px" }}>
                        <span
                          style={{
                            fontSize: "12px",
                            fontWeight: 600,
                            color: ex.is_active ? C.green : C.faint,
                          }}
                        >
                          {ex.is_active ? "● Ativo" : "○ Inativo"}
                        </span>
                      </td>
                      <td style={{ padding: "12px 16px", textAlign: "right", whiteSpace: "nowrap" }}>
                        <button onClick={() => setDetail(ex)} style={{ ...btn("transparent"), border: `1px solid ${C.border}`, color: C.muted, marginRight: "6px" }}>
                          Ver
                        </button>
                        <button onClick={() => openEdit(ex)} style={{ ...btn("transparent"), border: `1px solid ${C.border}`, color: C.muted, marginRight: "6px" }}>
                          Editar
                        </button>
                        <button
                          onClick={() => toggleActive(ex)}
                          style={{ ...btn("transparent"), border: `1px solid ${ex.is_active ? C.amber : C.green}`, color: ex.is_active ? C.amber : C.green }}
                        >
                          {ex.is_active ? "Desativar" : "Ativar"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* paginacao */}
        {totalPages > 1 && (
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "12px", marginTop: "16px" }}>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              style={{ ...btn("transparent"), border: `1px solid ${C.border}`, color: page <= 1 ? C.faint : C.muted, cursor: page <= 1 ? "not-allowed" : "pointer" }}
            >
              ← Anterior
            </button>
            <span style={{ color: C.muted, fontSize: "13px" }}>
              Pagina {page} de {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              style={{ ...btn("transparent"), border: `1px solid ${C.border}`, color: page >= totalPages ? C.faint : C.muted, cursor: page >= totalPages ? "not-allowed" : "pointer" }}
            >
              Proxima →
            </button>
          </div>
        )}
      </main>

      {formOpen && (
        <ExerciseFormModal
          headers={headers}
          allSlugs={items.map((e) => e.slug)}
          initial={editingSlug ? items.find((e) => e.slug === editingSlug) : undefined}
          onClose={() => setFormOpen(false)}
          onSaved={(text) => {
            setFormOpen(false);
            setMsg({ text, type: "success" });
            fetchList();
          }}
        />
      )}

      {detail && <ExerciseDetailModal ex={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

// ============================================================
// Modal de cadastro / edicao
// ============================================================
function ExerciseFormModal({
  headers,
  allSlugs,
  initial,
  onClose,
  onSaved,
}: {
  headers: Record<string, string>;
  allSlugs: string[];
  initial?: Exercise;
  onClose: () => void;
  onSaved: (text: string) => void;
}) {
  const isEdit = !!initial;
  const [form, setForm] = useState<FormState>(initial ? formFromExercise(initial) : emptyForm());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [subInput, setSubInput] = useState("");

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }));

  const addSub = () => {
    const s = subInput.trim();
    if (!s) return;
    if (s === form.slug) { setError("Substituicao nao pode referenciar o proprio exercicio."); return; }
    if (form.approved_substitutions.includes(s)) { setError("Substituicao ja adicionada."); return; }
    set("approved_substitutions", [...form.approved_substitutions, s]);
    setSubInput("");
    setError("");
  };
  const removeSub = (s: string) =>
    set("approved_substitutions", form.approved_substitutions.filter((x) => x !== s));

  const addMedia = () => set("media", [...form.media, { type: "video", url: "", alt: "" }]);
  const setMedia = (i: number, patch: Partial<Media>) =>
    set("media", form.media.map((m, idx) => (idx === i ? { ...m, ...patch } : m)));
  const removeMedia = (i: number) => set("media", form.media.filter((_, idx) => idx !== i));

  const submit = async () => {
    setError("");
    // validacoes de UX (o backend e a autoridade final)
    if (!form.name.trim() || !form.primary_muscle.trim() || !form.equipment.trim()) {
      setError("Preencha nome, grupo muscular e equipamento.");
      return;
    }
    if (!isEdit && !form.slug.trim()) {
      setError("Slug e obrigatorio.");
      return;
    }
    const media = form.media
      .map((m) => ({ type: m.type.trim(), url: m.url.trim(), alt: (m.alt || "").trim() || null }))
      .filter((m) => m.type || m.url);
    if (media.some((m) => !m.url)) {
      setError("Toda midia precisa de uma URL.");
      return;
    }

    const base = {
      name: form.name.trim(),
      primary_muscle: form.primary_muscle.trim(),
      equipment: form.equipment.trim(),
      level: form.level,
      secondary_muscles: csvToArray(form.secondary_muscles),
      instructions: form.instructions.trim() || null,
      common_errors: csvToArray(form.common_errors),
      cautions: csvToArray(form.cautions),
      approved_substitutions: form.approved_substitutions,
      media,
      is_active: form.is_active,
    };

    setSaving(true);
    try {
      let res: Response;
      if (isEdit && initial) {
        res = await fetch(`${API}/admin/exercises/${encodeURIComponent(initial.slug)}`, {
          method: "PATCH",
          headers,
          body: JSON.stringify(base),
        });
      } else {
        res = await fetch(`${API}/admin/exercises`, {
          method: "POST",
          headers,
          body: JSON.stringify({ slug: form.slug.trim(), ...base }),
        });
      }
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        const detailMsg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail || d);
        throw new Error(detailMsg || `Erro ${res.status}`);
      }
      onSaved(isEdit ? `Exercicio atualizado: ${initial!.slug}` : `Exercicio criado: ${form.slug.trim()}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <ModalShell title={isEdit ? `Editar exercicio — ${initial!.slug}` : "Novo exercicio"} onClose={onClose}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
        <div>
          <label style={labelStyle}>Slug {isEdit && <span style={{ color: C.faint }}>(imutavel)</span>}</label>
          <input
            style={{ ...inputStyle, opacity: isEdit ? 0.6 : 1 }}
            value={form.slug}
            disabled={isEdit}
            placeholder="supino-reto"
            onChange={(e) => set("slug", e.target.value)}
          />
        </div>
        <div>
          <label style={labelStyle}>Nome</label>
          <input style={inputStyle} value={form.name} placeholder="Ex: Supino reto" onChange={(e) => set("name", e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Grupo muscular</label>
          <input style={inputStyle} value={form.primary_muscle} placeholder="Ex: Peito" onChange={(e) => set("primary_muscle", e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Equipamento</label>
          <input style={inputStyle} value={form.equipment} placeholder="Ex: Barra" onChange={(e) => set("equipment", e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Nivel</label>
          <select style={inputStyle} value={form.level} onChange={(e) => set("level", e.target.value as Level)}>
            {LEVELS.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: "8px" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "8px", color: C.muted, fontSize: "14px", cursor: "pointer" }}>
            <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} />
            Ativo
          </label>
        </div>
      </div>

      <div style={{ marginTop: "12px" }}>
        <label style={labelStyle}>Musculos secundarios (separados por virgula)</label>
        <input style={inputStyle} value={form.secondary_muscles} onChange={(e) => set("secondary_muscles", e.target.value)} placeholder="Triceps, Ombro" />
      </div>
      <div style={{ marginTop: "12px" }}>
        <label style={labelStyle}>Instrucoes</label>
        <textarea
          style={{ ...inputStyle, height: "70px", resize: "vertical" }}
          value={form.instructions}
          onChange={(e) => set("instructions", e.target.value)}
        />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginTop: "12px" }}>
        <div>
          <label style={labelStyle}>Erros comuns (virgula)</label>
          <input style={inputStyle} value={form.common_errors} onChange={(e) => set("common_errors", e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Cuidados (virgula)</label>
          <input style={inputStyle} value={form.cautions} onChange={(e) => set("cautions", e.target.value)} />
        </div>
      </div>

      {/* substituicoes */}
      <div style={{ marginTop: "16px", borderTop: `1px solid ${C.border}`, paddingTop: "14px" }}>
        <label style={labelStyle}>Substituicoes aprovadas (slugs)</label>
        <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
          <input
            style={inputStyle}
            list="all-slugs"
            value={subInput}
            placeholder="slug do exercicio substituto"
            onChange={(e) => setSubInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addSub(); } }}
          />
          <datalist id="all-slugs">
            {allSlugs.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
          <button onClick={addSub} style={btn(C.accent)}>Adicionar</button>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {form.approved_substitutions.map((s) => (
            <span key={s} style={{ display: "inline-flex", alignItems: "center", gap: "6px", background: C.bg, border: `1px solid ${C.border}`, borderRadius: "20px", padding: "4px 10px", fontSize: "13px" }}>
              {s}
              <span style={{ cursor: "pointer", color: C.red }} onClick={() => removeSub(s)}>×</span>
            </span>
          ))}
          {form.approved_substitutions.length === 0 && <span style={{ color: C.faint, fontSize: "13px" }}>Nenhuma.</span>}
        </div>
      </div>

      {/* midia */}
      <div style={{ marginTop: "16px", borderTop: `1px solid ${C.border}`, paddingTop: "14px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <label style={{ ...labelStyle, marginBottom: 0 }}>Midia</label>
          <button onClick={addMedia} style={{ ...btn("transparent"), border: `1px solid ${C.border}`, color: C.muted }}>+ Midia</button>
        </div>
        {form.media.map((m, i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "120px 2fr 1fr auto", gap: "8px", marginBottom: "8px" }}>
            <select style={inputStyle} value={m.type} onChange={(e) => setMedia(i, { type: e.target.value })}>
              <option value="video">video</option>
              <option value="image">image</option>
              <option value="gif">gif</option>
            </select>
            <input style={inputStyle} value={m.url} placeholder="https://..." onChange={(e) => setMedia(i, { url: e.target.value })} />
            <input style={inputStyle} value={m.alt ?? ""} placeholder="alt (opcional)" onChange={(e) => setMedia(i, { alt: e.target.value })} />
            <button onClick={() => removeMedia(i)} style={{ ...btn("transparent"), border: `1px solid ${C.red}`, color: C.red }}>×</button>
          </div>
        ))}
        {form.media.length === 0 && <span style={{ color: C.faint, fontSize: "13px" }}>Nenhuma midia.</span>}
      </div>

      {error && <p style={{ color: "#fca5a5", fontSize: "13px", marginTop: "14px" }}>{error}</p>}

      <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "18px" }}>
        <button onClick={onClose} style={{ ...btn("transparent"), border: `1px solid ${C.border}`, color: C.muted }}>Cancelar</button>
        <button onClick={submit} disabled={saving} style={btn(C.green)}>
          {saving ? "Salvando..." : isEdit ? "Salvar alteracoes" : "Criar exercicio"}
        </button>
      </div>
    </ModalShell>
  );
}

// ============================================================
// Modal de detalhe (inclui visualizacao de midia)
// ============================================================
function ExerciseDetailModal({ ex, onClose }: { ex: Exercise; onClose: () => void }) {
  const line = (label: string, value: React.ReactNode) => (
    <div style={{ marginBottom: "10px" }}>
      <p style={{ color: C.faint, fontSize: "11px", fontWeight: 600, textTransform: "uppercase", marginBottom: "2px" }}>{label}</p>
      <div style={{ color: "white", fontSize: "14px" }}>{value}</div>
    </div>
  );
  const chips = (arr: string[]) =>
    arr.length ? (
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
        {arr.map((x) => (
          <span key={x} style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: "16px", padding: "3px 10px", fontSize: "13px" }}>{x}</span>
        ))}
      </div>
    ) : (
      <span style={{ color: C.faint }}>—</span>
    );

  return (
    <ModalShell title={`${ex.name} — ${ex.slug}`} onClose={onClose}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
        {line("Grupo muscular", ex.primary_muscle)}
        {line("Equipamento", ex.equipment)}
        {line("Nivel", ex.level)}
        {line("Status", <span style={{ color: ex.is_active ? C.green : C.faint }}>{ex.is_active ? "Ativo" : "Inativo"}</span>)}
      </div>
      {line("Musculos secundarios", chips(ex.secondary_muscles))}
      {line("Instrucoes", ex.instructions || <span style={{ color: C.faint }}>—</span>)}
      {line("Erros comuns", chips(ex.common_errors))}
      {line("Cuidados", chips(ex.cautions))}
      {line("Substituicoes aprovadas", chips(ex.approved_substitutions))}

      <div style={{ borderTop: `1px solid ${C.border}`, margin: "14px 0", paddingTop: "8px" }} />
      <p style={{ color: C.faint, fontSize: "11px", fontWeight: 600, textTransform: "uppercase", marginBottom: "10px" }}>Midia</p>
      {ex.media.length === 0 ? (
        <span style={{ color: C.faint, fontSize: "14px" }}>Nenhuma midia.</span>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "12px" }}>
          {ex.media.map((m, i) => (
            <div key={i} style={{ width: "180px", background: C.bg, border: `1px solid ${C.border}`, borderRadius: "8px", padding: "8px" }}>
              {m.type === "image" || m.type === "gif" ? (
                <img src={m.url} alt={m.alt ?? ex.name} style={{ width: "100%", borderRadius: "6px", display: "block" }} />
              ) : (
                <div style={{ fontSize: "13px", color: C.muted, wordBreak: "break-all" }}>
                  🎬 <a href={m.url} target="_blank" rel="noreferrer" style={{ color: "#93c5fd" }}>{m.url}</a>
                </div>
              )}
              <p style={{ fontSize: "11px", color: C.faint, marginTop: "6px" }}>{m.type}{m.alt ? ` · ${m.alt}` : ""}</p>
            </div>
          ))}
        </div>
      )}
    </ModalShell>
  );
}

// ============================================================
// Shell reutilizavel de modal
// ============================================================
function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "20px" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{ background: C.card, borderRadius: "16px", maxWidth: "720px", width: "100%", border: `1px solid ${C.border}`, maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "20px 24px", borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ color: "white", fontSize: "17px", fontWeight: 700 }}>{title}</h2>
          <button onClick={onClose} style={{ background: C.border, color: "white", border: "none", padding: "6px 12px", borderRadius: "8px", cursor: "pointer", fontSize: "16px" }}>×</button>
        </div>
        <div style={{ padding: "20px 24px", overflowY: "auto" }}>{children}</div>
      </div>
    </div>
  );
}
