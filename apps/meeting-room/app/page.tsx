"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// The API address: ?api=https://... in the URL (remembered), else the build-time env, else local dev.
const API = (() => {
  const fallback = process.env.NEXT_PUBLIC_ROUNDTABLE_API ?? "http://127.0.0.1:8788";
  if (typeof window === "undefined") return fallback;
  try {
    const q = new URLSearchParams(window.location.search).get("api");
    if (q) localStorage.setItem("api", q);
    return q ?? localStorage.getItem("api") ?? fallback;
  } catch {
    return fallback;
  }
})();

type ModelSettings = { provider: string; model: string; base_url: string; api_key: string };
const DEFAULT_SETTINGS: ModelSettings = { provider: "mock", model: "auto", base_url: "https://api.openai.com/v1", api_key: "" };
let modelSettings: ModelSettings = DEFAULT_SETTINGS;
function loadSettings(): ModelSettings {
  try {
    const raw = localStorage.getItem("model-settings");
    if (raw) modelSettings = { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {}
  return modelSettings;
}
function saveSettings(s: ModelSettings) {
  modelSettings = s;
  try {
    localStorage.setItem("model-settings", JSON.stringify(s));
  } catch {}
}

type Msg = { id: number; meeting_id: string; round: string; kind: string; from_agent: string; to_agent: string; refs: string[]; text: string; ts: number };
type Entry = { id: string; kind: string; owner: string; version: number; status: string; payload: any; evidence: any[] };
type Decision = { id: string; kind: string; ref: string; text: string; options: string[] };
type MeetingData = {
  meeting: { id: string; title: string; status: string; round: string; waiting?: Decision[] | null; model?: string };
  rounds: string[];
  blackboard: Record<string, Entry[]>;
  turns: any[];
  cost: { tokens: number; usd: number; calls: number };
  db: string;
};
type ServerSettings = { anthropic_models: string[]; server_default: string; label: string };

const SEATS = ["chair", "researcher", "scoper", "estimator", "pricer", "risk", "writer", "critic", "arbiter", "you"];
const AGENDA = ["brief", "research", "scope", "estimate", "price", "draft", "critique", "reconcile", "human_seat", "finalise"];
const ROUND_LABEL: Record<string, string> = { brief: "Brief", research: "Research", scope: "Scope", estimate: "Estimate", price: "Price + Risk", draft: "Draft", critique: "Critique", reconcile: "Reconcile", human_seat: "Your seat", finalise: "Finalise" };
const TABS = ["requirements", "findings", "packages", "estimates", "pricing", "risks", "draft", "objections", "outputs"] as const;

async function api(path: string, init?: RequestInit) {
  const s = modelSettings;
  const headers: Record<string, string> = { "content-type": "application/json", "x-model-provider": s.provider, "x-model-name": s.model, "x-model-base-url": s.base_url };
  if (s.api_key) headers["x-model-key"] = s.api_key;
  const r = await fetch(API + path, { ...init, headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) } });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

function modelLabel(s: ModelSettings) {
  if (s.provider === "anthropic") return `Anthropic · ${s.model === "auto" ? "Opus 5 + Sonnet 5" : s.model}`;
  if (s.provider === "openai") {
    try {
      return `${s.model} @ ${new URL(s.base_url).host}`;
    } catch {
      return s.model;
    }
  }
  return "Mock · no key";
}

export default function MeetingRoom() {
  const [mid, setMid] = useState<string | null>(null);
  const [data, setData] = useState<MeetingData | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [tab, setTab] = useState<(typeof TABS)[number]>("requirements");
  const [settings, setSettings] = useState<ModelSettings>(DEFAULT_SETTINGS);
  const [server, setServer] = useState<ServerSettings | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [offline, setOffline] = useState(false);
  const [stepping, setStepping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastMsg = useRef(0);
  const steppingRef = useRef(false);
  const transcriptRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async (id: string) => {
    try {
      const d = await api(`/api/meetings/${id}`);
      setData(d);
      setOffline(false);
      return d as MeetingData;
    } catch {
      setOffline(true);
      return null;
    }
  }, []);

  const pollMessages = useCallback(async (id: string) => {
    try {
      const r = await api(`/api/meetings/${id}/messages?after=${lastMsg.current}`);
      if (r.messages?.length) {
        lastMsg.current = r.last_id;
        setMessages((prev) => [...prev, ...r.messages]);
      }
    } catch {}
  }, []);

  // the UI is the Chair's clock: one round per request until the meeting finishes or needs you
  const drive = useCallback(async (id: string) => {
    if (steppingRef.current) return;
    steppingRef.current = true;
    setStepping(true);
    setError(null);
    try {
      for (let i = 0; i < 20; i++) {
        const r = await api(`/api/meetings/${id}/step`, { method: "POST" });
        await pollMessages(id);
        await refresh(id);
        if (r.finished || r.waiting) break;
      }
    } catch (e: any) {
      setError(String(e.message ?? e));
    } finally {
      steppingRef.current = false;
      setStepping(false);
      refresh(id);
    }
  }, [pollMessages, refresh]);

  useEffect(() => {
    setSettings(loadSettings());
    api("/api/settings").then(setServer).catch(() => {});
    api("/api/meetings").then((l) => { if (l.meetings?.length) setMid(l.meetings[0].id); }).catch(() => setOffline(true));
  }, []);

  useEffect(() => {
    if (!mid) return;
    lastMsg.current = 0;
    setMessages([]);
    pollMessages(mid);
    refresh(mid).then((d) => { if (d && d.meeting.status === "running") drive(mid); });
    const t1 = setInterval(() => pollMessages(mid), 1000);
    const t2 = setInterval(() => refresh(mid), 4000);
    return () => { clearInterval(t1); clearInterval(t2); };
  }, [mid, pollMessages, refresh, drive]);

  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  const status = data?.meeting.status ?? "idle";
  const round = data?.meeting.round ?? "";
  const waiting = status === "waiting_for_human" ? (data?.meeting.waiting ?? []) : [];
  const activeAgents = useMemo(() => {
    const recent = messages.slice(-6);
    const s = new Set<string>();
    if (status === "running") for (const m of recent) { if (m.kind === "assign") s.add(m.to_agent); if (m.kind === "fanout") s.add(m.from_agent); }
    if (waiting.length) s.add("you");
    return s;
  }, [messages, waiting, status]);
  const bb = data?.blackboard ?? {};
  const current = (k: string) => (bb[k] ?? []).filter((e) => e.status !== "superseded");

  const start = async () => {
    setError(null);
    try {
      const r = await api("/api/meetings", { method: "POST" });
      setMid(r.id);
      setTimeout(() => drive(r.id), 50);
    } catch (e: any) {
      setError(String(e.message ?? e));
    }
  };
  const reset = async () => { await api("/api/demo/reset", { method: "POST" }); setMid(null); setData(null); setMessages([]); lastMsg.current = 0; };
  const settle = async (answers: Record<string, { decision: string; note: string }>) => {
    if (!mid) return;
    setError(null);
    try {
      await api(`/api/meetings/${mid}/human`, { method: "POST", body: JSON.stringify({ answers }) });
      await pollMessages(mid);
      await refresh(mid);
      drive(mid);
    } catch (e: any) {
      setError(String(e.message ?? e));
    }
  };

  return (
    <>
      <header className="top">
        <div className="brand">
          <span className="name">Roundtable</span>
          <span className="mono dim">meeting room · Harbor Logistics RFP</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className={`badge ${stepping || status === "running" ? "accent" : status === "waiting_for_human" ? "warn" : status === "finished" ? "ok" : ""}`}>
            <span className={`dot ${stepping ? "pulse" : ""}`} /> {status === "waiting_for_human" ? "waiting for you" : offline ? "api offline" : stepping ? "in session" : status}
          </span>
          <button className="btn sm" onClick={() => setShowSettings((s) => !s)} title={data?.db}>{modelLabel(settings)}</button>
          <button className="btn sm" onClick={reset} disabled={stepping}>Reset</button>
          <button className="btn primary sm" onClick={start} disabled={stepping || status === "running" || status === "waiting_for_human"}>Open the meeting →</button>
        </div>
      </header>

      {showSettings ? <SettingsPanel settings={settings} server={server} onChange={(s) => { setSettings(s); saveSettings(s); }} onClose={() => setShowSettings(false)} judgmentNote="auto · Opus 5 for the Chair, Critic and Arbiter; Sonnet 5 for the rest" /> : null}

      <main className="grid" style={{ gridTemplateColumns: "300px minmax(0, 1fr) 420px" }}>
        <section className="col">
          <div className="card">
            <h2>Agenda</h2>
            <ol className="agenda">
              {AGENDA.map((r) => {
                const idx = AGENDA.indexOf(r);
                const cur = AGENDA.indexOf(round);
                const state = status === "finished" ? "done" : idx < cur ? "done" : idx === cur && status !== "idle" ? "now" : "todo";
                return <li key={r} data-state={state}><span className="dot" />{ROUND_LABEL[r]}</li>;
              })}
            </ol>
          </div>
          <div className="card">
            <h2>The table</h2>
            <ul className="seats">
              {SEATS.map((s) => (
                <li key={s} data-active={activeAgents.has(s)} data-you={s === "you"}>
                  <span className="seat-dot" /> {s}
                </li>
              ))}
            </ul>
          </div>
          <div className="card">
            <h2>Meeting</h2>
            {data ? (
              <div className="stats">
                <div className="stat"><span className="v">{data.turns.length}</span><span className="l">turns</span></div>
                <div className="stat"><span className="v">{current("objection").length}</span><span className="l">objections</span></div>
                <div className="stat"><span className="v">${data.cost.usd.toFixed(2)}</span><span className="l">{data.cost.tokens.toLocaleString()} tokens</span></div>
                <div className="stat"><span className="v">{(current("score").find((e) => e.payload.criterion === "weighted")?.payload.score ?? "–")}</span><span className="l">critic score /100</span></div>
              </div>
            ) : <div className="note">Press “Open the meeting” to start on the Harbor Logistics RFP.</div>}
            {data?.meeting.model ? <div className="note" style={{ marginTop: 8 }}>Model: {data.meeting.model} · Store: {data.db}</div> : null}
          </div>
        </section>

        <section className="col">
          {error ? <div className="card" style={{ borderColor: "var(--bad)" }}><div className="note" style={{ color: "var(--bad)" }}>{error}</div></div> : null}
          {waiting.length ? <Seat decisions={waiting} onSettle={settle} /> : null}
          <div className="card" style={{ flex: 1, minHeight: 400, display: "flex", flexDirection: "column" }}>
            <h2>Transcript · {messages.length} messages</h2>
            <div ref={transcriptRef} className="transcript">
              {messages.length === 0 ? <div className="note">Every assignment, delivery, objection, defence and ruling appears here. This is also the minutes.</div> : null}
              {messages.map((m) => (
                <div key={m.id} className="msg" data-kind={m.kind}>
                  <div className="msg-head">
                    <span className="who">{m.from_agent}</span>
                    {m.to_agent !== "all" ? <span className="dim">→ {m.to_agent}</span> : null}
                    <span className={`badge ${kindClass(m.kind)}`}>{m.kind}</span>
                    <span className="mono dim">{m.round}</span>
                  </div>
                  <div className="msg-text">{m.text}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <aside className="col">
          <div className="card" style={{ flex: 1 }}>
            <div className="tabs">
              {TABS.map((t) => <button key={t} className="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t}{countFor(t, bb) ? <span className="cnt">{countFor(t, bb)}</span> : null}</button>)}
            </div>
            <Blackboard tab={tab} bb={bb} />
          </div>
        </aside>
      </main>
    </>
  );
}

function Seat({ decisions, onSettle }: { decisions: Decision[]; onSettle: (a: Record<string, { decision: string; note: string }>) => Promise<void> }) {
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const ready = decisions.every((d) => picked[d.id]);
  return (
    <div className="card you">
      <h2>Your seat · {decisions.length} decision{decisions.length !== 1 ? "s" : ""}</h2>
      <div style={{ display: "grid", gap: 12 }}>
        {decisions.map((d) => (
          <div key={d.id} className="row" style={{ background: "#fff" }}>
            <div className="row-head"><span className="badge">{d.kind}</span><span className="mono dim">{d.ref}</span></div>
            <p style={{ margin: "4px 0 8px", fontSize: 13.5 }}>{d.text}</p>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {d.options.map((o) => <button key={o} className={`btn sm ${picked[d.id] === o ? "primary" : ""}`} onClick={() => setPicked((p) => ({ ...p, [d.id]: o }))}>{o}</button>)}
            </div>
            <input className="noteinput" style={{ marginTop: 8 }} value={notes[d.id] ?? ""} onChange={(e) => setNotes((n) => ({ ...n, [d.id]: e.target.value }))} placeholder="Optional note for the minutes" />
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 12 }}>
        <button className="btn primary sm" disabled={!ready || busy} onClick={async () => { setBusy(true); try { await onSettle(Object.fromEntries(decisions.map((d) => [d.id, { decision: picked[d.id], note: notes[d.id] ?? "" }]))); } finally { setBusy(false); } }}>
          Send decisions and resume the meeting
        </button>
        {!ready ? <span className="note">Pick an option for each item.</span> : null}
      </div>
    </div>
  );
}

function countFor(tab: string, bb: Record<string, Entry[]>) {
  const cur = (k: string) => (bb[k] ?? []).filter((e) => e.status !== "superseded").length;
  return { requirements: cur("requirement"), findings: cur("finding"), packages: cur("work_package"), estimates: cur("estimate"), pricing: cur("price_line"), risks: cur("risk"), draft: cur("section"), objections: cur("objection"), outputs: cur("output") }[tab] ?? 0;
}

function kindClass(k: string) {
  return { objection: "bad", ruling: "blue", defence: "warn", revision: "ok", escalate: "warn", human: "ok", error: "bad", reject: "bad", warning: "warn", deliver: "ok", fanout: "accent", parallel: "accent", done: "ok" }[k] ?? "";
}

function Blackboard({ tab, bb }: { tab: string; bb: Record<string, Entry[]> }) {
  const cur = (k: string) => (bb[k] ?? []).filter((e) => e.status !== "superseded");
  if (tab === "requirements") {
    const reqs = cur("requirement");
    const qs = cur("question");
    if (!reqs.length) return <Empty what="The Scoper's requirements matrix" />;
    return (
      <div className="bb">
        {reqs.map((e) => (
          <div key={e.id} className="row">
            <div className="row-head"><strong>{e.payload.id}</strong><span className={`badge ${e.payload.priority === "must" ? "bad" : e.payload.priority === "should" ? "warn" : ""}`}>{e.payload.priority}</span><span className="mono dim">p{e.payload.page}</span></div>
            <div className="ink2">{e.payload.text}</div>
          </div>
        ))}
        {qs.length ? <h3 style={{ marginTop: 12 }}>Questions for the client</h3> : null}
        {qs.map((e) => <div key={e.id} className="row"><div>{e.payload.text}</div><div className="note">{e.payload.why} · raised by {e.owner}</div></div>)}
      </div>
    );
  }
  if (tab === "findings") {
    const f = cur("finding");
    if (!f.length) return <Empty what="The Researcher's findings" />;
    return <div className="bb">{f.map((e) => <div key={e.id} className="row"><div>{e.payload.text}</div><div className="note">source: {e.payload.source_id} · confidence {Math.round(e.payload.confidence * 100)}%</div></div>)}</div>;
  }
  if (tab === "packages") {
    const p = cur("work_package");
    if (!p.length) return <Empty what="Work packages" />;
    return <div className="bb">{p.map((e) => <div key={e.id} className="row"><div className="row-head"><strong>{e.payload.id} · {e.payload.name}</strong>{e.payload.optional ? <span className="badge">option</span> : null}</div><div className="note">{e.payload.requirement_ids.join(", ")} · {e.payload.assumptions.join("; ") || "no assumptions"}</div></div>)}</div>;
  }
  if (tab === "estimates") {
    const ests = cur("estimate").filter((e) => e.id !== "est:reconciliation");
    const rec = cur("estimate").find((e) => e.id === "est:reconciliation");
    if (!ests.length) return <Empty what="Sub-estimates and the reconciliation" />;
    return (
      <div className="bb">
        {rec ? <div className="row accent-row"><strong>Reconciliation · {rec.payload.total_days} days</strong><div className="ink2">{rec.payload.note}</div>{rec.payload.flags?.map((f: any) => <div key={f.package_id} className="flag">⚑ {f.package_id}: {f.note}</div>)}</div> : null}
        {ests.map((e) => {
          const days = e.payload.days_by_role.reduce((a: number, r: any) => a + r.days, 0);
          const alt = e.payload.alternatives?.[0];
          const altDays = alt ? alt.days_by_role.reduce((a: number, r: any) => a + r.days, 0) : null;
          return (
            <div key={e.id} className="row">
              <div className="row-head"><strong>{e.payload.package_id}</strong><span className="badge">{days.toFixed(1)} d</span>{altDays !== null ? <span className={`badge ${Math.abs(altDays - days) / Math.max(altDays, days) > 0.25 ? "bad" : ""}`}>2nd estimate {altDays.toFixed(1)} d</span> : null}</div>
              <div className="note">{e.payload.days_by_role.map((r: any) => `${r.role} ${r.days}`).join(" · ")}</div>
              <div className="note">{e.payload.rationale}</div>
            </div>
          );
        })}
      </div>
    );
  }
  if (tab === "pricing") {
    const s = cur("pricing")[0];
    const lines = cur("price_line");
    if (!s) return <Empty what="The price" />;
    const p = s.payload;
    return (
      <div className="bb">
        <div className="row accent-row">
          <div className="stats"><div className="stat"><span className="v">${p.total.toLocaleString()}</span><span className="l">fixed price</span></div><div className="stat"><span className="v">{Math.round(p.margin * 100)}%</span><span className="l">margin · floor {Math.round(p.floor_margin * 100)}%</span></div></div>
          <div className="ink2" style={{ marginTop: 8 }}>{p.summary}</div>
          {p.deviations.map((d: any) => <div key={d.package_id} className="flag">{d.package_id} {d.percent}% · {d.reason} · cites {d.comparable_id}</div>)}
          <div className="note">Options: ${p.options_total.toLocaleString()}</div>
        </div>
        <table className="rows"><thead><tr><th>Package</th><th>Role</th><th>Days</th><th>Rate</th><th>Amount</th></tr></thead>
          <tbody>{lines.map((l) => <tr key={l.id} style={{ opacity: l.payload.optional ? 0.55 : 1 }}><td>{l.payload.package_id}</td><td>{l.payload.role}</td><td>{l.payload.days}</td><td>{l.payload.rate}</td><td>{l.payload.amount.toLocaleString()}</td></tr>)}</tbody></table>
      </div>
    );
  }
  if (tab === "risks") {
    const r = cur("risk");
    if (!r.length) return <Empty what="The risk register" />;
    return <div className="bb">{r.map((e) => <div key={e.id} className="row"><div className="row-head"><span className={`badge ${e.payload.severity === "high" ? "bad" : e.payload.severity === "medium" ? "warn" : ""}`}>{e.payload.severity}</span><span className={`badge ${e.payload.stance === "decline" ? "bad" : e.payload.stance === "negotiate" ? "warn" : "ok"}`}>{e.payload.stance}</span>{e.payload.decision ? <span className="badge ok">you: {e.payload.decision}</span> : null}<span className="mono dim">p{e.payload.page}</span></div><div className="quote">“{e.payload.quote}”</div><div className="ink2">{e.payload.position}</div>{e.payload.playbook_id ? <div className="note">playbook: {e.payload.playbook_id}</div> : null}</div>)}</div>;
  }
  if (tab === "draft") {
    const secs = cur("section");
    if (!secs.length) return <Empty what="The draft" />;
    return <div className="bb">{secs.map((e) => <div key={e.id} className="row"><div className="row-head"><strong>{e.payload.title}</strong><span className="badge">v{e.version}</span></div><div className="draft" style={{ fontSize: 13 }}>{e.payload.body}</div><div className="note">cites: {e.payload.citations.join(", ")}{e.payload.dangling?.length ? ` · not in evidence: ${e.payload.dangling.join(", ")}` : ""}</div></div>)}</div>;
  }
  if (tab === "objections") {
    const o = cur("objection");
    const sc = cur("score");
    if (!o.length && !sc.length) return <Empty what="The Critic's scores and objections" />;
    return (
      <div className="bb">
        {sc.length ? <div className="row accent-row"><strong>Scores</strong>{sc.map((e) => <div key={e.id} className="note"><strong>{e.payload.criterion}</strong> {e.payload.score}{e.payload.criterion === "weighted" ? "/100" : "/10"} · {e.payload.reason}</div>)}</div> : null}
        {o.map((e) => <div key={e.id} className="row"><div className="row-head"><strong>{e.id}</strong><span className="mono dim">on {e.payload.target_id}</span><span className={`badge ${e.status === "open" ? "warn" : e.status === "accepted" || e.status === "upheld" ? "ok" : e.status === "overruled" ? "blue" : ""}`}>{e.status}</span></div><div>{e.payload.claim}</div><div className="note">evidence: {e.payload.evidence_ids.join(", ")} · proposed: {e.payload.proposed_resolution}</div></div>)}
      </div>
    );
  }
  if (tab === "outputs") {
    const outs = cur("output");
    if (!outs.length) return <Empty what="The proposal, pricing sheet, risk register, client Q&A and minutes" />;
    return <div className="bb">{outs.map((e) => <details key={e.id} className="row" open={e.payload.name === "proposal"}><summary><strong>{e.payload.name.replace("_", " ")}</strong> <span className="note">{e.payload.text.length.toLocaleString()} chars</span></summary><pre className="doc" style={{ maxHeight: 420 }}>{e.payload.text}</pre><button className="btn sm" style={{ marginTop: 6 }} onClick={() => { const b = new Blob([e.payload.text], { type: "text/plain" }); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `${e.payload.name}.${e.payload.name === "pricing_sheet" ? "csv" : "md"}`; a.click(); }}>Download</button></details>)}</div>;
  }
  return null;
}

function Empty({ what }: { what: string }) {
  return <div className="empty">{what} will appear here.</div>;
}

function SettingsPanel({ settings, server, onChange, onClose, judgmentNote }: { settings: ModelSettings; server: ServerSettings | null; onChange: (s: ModelSettings) => void; onClose: () => void; judgmentNote?: string }) {
  const [provider, setProvider] = useState(settings.provider);
  const [model, setModel] = useState(settings.model);
  const [baseUrl, setBaseUrl] = useState(settings.base_url);
  const [key, setKey] = useState(settings.api_key);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const models = server?.anthropic_models ?? ["auto", "claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"];
  const save = async () => {
    setBusy(true);
    const next: ModelSettings = { provider, model: provider === "anthropic" && !models.includes(model) ? "auto" : model, base_url: baseUrl, api_key: provider === "mock" ? "" : key };
    onChange(next);
    try {
      setStatus("Saved in this browser. Checking…");
      const c = await api("/api/settings/check", { method: "POST" });
      setStatus((c.ok ? "✓ " : "✗ ") + c.detail);
    } catch (e: any) {
      setStatus("✗ " + String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="card" style={{ margin: "16px 20px 0", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0 20px" }}>
      <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h2>Model · bring your own key</h2>
        <button className="btn sm" onClick={onClose}>Close</button>
      </div>
      <div className="field">
        <label>Provider</label>
        <select value={provider} onChange={(e) => { setProvider(e.target.value); setModel(e.target.value === "anthropic" ? "auto" : e.target.value === "openai" ? "gpt-4o" : "mock"); }}>
          <option value="mock">Mock · deterministic, no key</option>
          <option value="anthropic">Anthropic · Claude</option>
          <option value="openai">OpenAI-compatible · OpenAI, vLLM, Ollama, …</option>
        </select>
      </div>
      {provider === "anthropic" ? (
        <div className="field"><label>Model</label><select value={model} onChange={(e) => setModel(e.target.value)}>{models.map((m) => <option key={m} value={m}>{m === "auto" ? (judgmentNote ?? "auto") : m}</option>)}</select></div>
      ) : null}
      {provider === "openai" ? (
        <>
          <div className="field"><label>Model</label><input value={model} onChange={(e) => setModel(e.target.value)} placeholder="gpt-4o, llama-3.3-70b, …" /></div>
          <div className="field"><label>Base URL</label><input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1 or http://localhost:8000/v1" /></div>
        </>
      ) : null}
      {provider !== "mock" ? (
        <div className="field"><label>API key</label><input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="paste your key" autoComplete="off" /></div>
      ) : null}
      <div style={{ gridColumn: "1 / -1", display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <button className="btn primary sm" onClick={save} disabled={busy}>Save and test</button>
        <span className="note">{status ?? "Your key stays in this browser and is sent only with your own requests, straight to the provider you chose. The server never stores it."}</span>
      </div>
    </div>
  );
}
