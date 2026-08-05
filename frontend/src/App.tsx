import { useState, useEffect, useCallback } from 'react';
import './App.css';
import { MapView } from './MapView';
import type { Ticket, DtOverview, SimDt } from './types';

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const SIM = import.meta.env.VITE_SIM_URL ?? 'http://localhost:8081';

const LIFECYCLE = ['detected', 'acknowledged', 'assigned', 'resolved', 'verified', 'closed'] as const;

// ─── Severity helper ─────────────────────────────────────────────

function severity(t: Ticket): 'critical' | 'high' | 'medium' | 'low' {
  if (t.affected_poles_count >= 50) return 'critical';
  if (t.affected_poles_count >= 20) return 'high';
  if (t.affected_poles_count >= 8)  return 'medium';
  return 'low';
}

// ─── Lifecycle bar ────────────────────────────────────────────────

function LifecycleBar({ status }: { status: string }) {
  const cur = LIFECYCLE.indexOf(status as typeof LIFECYCLE[number]);
  return (
    <div className="lifecycle-bar">
      {LIFECYCLE.map((step, i) => (
        <div
          key={step}
          className={`lc-step${i < cur ? ' done' : ''}${i === cur ? ' current' : ''}`}
        >
          <div className="lc-dot" />
          <span className="lc-label">{step}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Ticket card ─────────────────────────────────────────────────

interface TicketCardProps {
  ticket: Ticket;
  isSelected: boolean;
  onSelect: () => void;
  onAction: (action: string) => void;
  actionError: string | null;
}

function TicketCard({ ticket: t, isSelected, onSelect, onAction, actionError }: TicketCardProps) {
  const sev = severity(t);
  const isActive = !['verified', 'closed'].includes(t.status);

  return (
    <article
      className={`ticket-card sev-${sev}${isSelected ? ' selected' : ''}${!isActive ? ' inactive' : ''}`}
      onClick={onSelect}
      onKeyDown={event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect();
        }
      }}
      role="button"
      tabIndex={0}
      aria-expanded={isSelected}
      aria-label={`Ticket ${t.id} for ${t.dt_id}, ${t.status}`}
    >
      {/* ── Top row ── */}
      <div className="tc-top">
        <div className="tc-left">
          {(sev === 'critical' || sev === 'high') && (
            <span className={`sev-badge sev-badge-${sev}`}>
              {sev === 'critical' ? '🔴 CRITICAL' : '🟠 HIGH'}
            </span>
          )}
          <span className="tc-dt">{t.dt_id}</span>
          {t.feeder_id && <span className="tc-feeder">F:{t.feeder_id}</span>}
        </div>
        <span className={`status-pill s-${t.status}`}>{t.status.toUpperCase()}</span>
      </div>

      {/* ── Middle row ── */}
      <div className="tc-mid">
        <span className="tc-ftype">{t.fault_boundary?.type?.replace('_', ' ')}</span>
        {t.is_geometric_inference && (
          <span className="tc-inferred" title={t.confidence_reason}>⚠ INFERRED</span>
        )}
        <span className={`conf-badge conf-${t.confidence?.toLowerCase()}`}>
          {t.confidence}
        </span>
      </div>

      {/* ── Summary ── */}
      <div className="tc-summary">
        <span>📍 {t.fault_boundary?.first_dark ?? t.dt_id}</span>
        <span>🔌 {t.affected_poles_count} poles</span>
        {t.fault_pincode && <span>📮 {t.fault_pincode}</span>}
      </div>

      {/* ── Expanded detail (Item 2) ── */}
      {isSelected && (
        <div className="tc-expanded" onClick={e => e.stopPropagation()}>
          <LifecycleBar status={t.status} />

          <div className="tc-detail">
            <div className="td-row">
              <span className="td-label">Span</span>
              <span>{t.fault_boundary?.last_live} → {t.fault_boundary?.first_dark}</span>
            </div>
            <div className="td-row">
              <span className="td-label">Confidence</span>
              <span className={`conf-badge conf-${t.confidence?.toLowerCase()}`}>{t.confidence}</span>
            </div>
            <div className="td-row">
              <span className="td-label">Why</span>
              <span className="td-reason">{t.confidence_reason}</span>
            </div>
            {t.fault_lat != null && t.fault_lon != null && (
              <div className="td-row">
                <span className="td-label">Drive to</span>
                <a
                  href={`https://www.google.com/maps?q=${t.fault_lat},${t.fault_lon}`}
                  target="_blank"
                  rel="noreferrer"
                  className="td-coords"
                >
                  {t.fault_lat.toFixed(5)}, {t.fault_lon.toFixed(5)} ↗
                </a>
              </div>
            )}
            {t.fault_pincode && (
              <div className="td-row">
                <span className="td-label">PIN code</span>
                <span>{t.fault_pincode}</span>
              </div>
            )}
            <div className="td-row">
              <span className="td-label">Feeder</span>
              <span>{t.feeder_id ?? '—'}</span>
            </div>
            <div className="td-row">
              <span className="td-label">Opened</span>
              <span>{new Date(t.created_at).toLocaleString()}</span>
            </div>
            {t.resolved_at && (
              <div className="td-row">
                <span className="td-label">Resolved</span>
                <span>{new Date(t.resolved_at).toLocaleString()}</span>
              </div>
            )}
          </div>

          {/* ── Rejection banner (Item 3) ── */}
          {actionError && (
            <div className="action-error">
              <span className="ae-icon">⚠️</span>
              <span>{actionError}</span>
            </div>
          )}

          {/* ── Lifecycle controls (Item 3) ── */}
          <div className="tc-actions">
            {t.status === 'detected' && (
              <button className="btn btn-blue" onClick={() => onAction('acknowledge')}>
                Acknowledge
              </button>
            )}
            {t.status === 'acknowledged' && (
              <button className="btn btn-orange" onClick={() => onAction('assign')}>
                Dispatch Crew
              </button>
            )}
            {t.status === 'assigned' && (
              <button className="btn btn-green" onClick={() => onAction('resolve')}
                title="Crew reports fix complete. Rejected if poles still dark.">
                Mark Fixed (crew report)
              </button>
            )}
            {t.status === 'resolved' && (
              <p className="tc-awaiting">⏳ Awaiting telemetry confirmation — auto-verifies when poles go live.</p>
            )}
            {t.status === 'verified' && (
              <button className="btn btn-muted" onClick={() => onAction('close')}>
                Close Ticket
              </button>
            )}
          </div>
        </div>
      )}
    </article>
  );
}

// ─── Simulator panel (Item 5) ─────────────────────────────────────

function SimulatorPanel() {
  const [dts, setDts]             = useState<SimDt[]>([]);
  const [feeders, setFeeders]     = useState<string[]>([]);
  const [faultType, setFaultType] = useState<'span_fault' | 'dt_fault' | 'feeder_fault'>('span_fault');
  const [target, setTarget]       = useState('');
  const [feeder, setFeeder]       = useState('');
  const [fastMode, setFastMode]   = useState(true);
  const [log, setLog]             = useState<string[]>([]);

  const addLog = (msg: string) =>
    setLog(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 25));

  useEffect(() => {
    fetch(`${SIM}/dts`)
      .then(r => r.json())
      .then((data: SimDt[]) => {
        setDts(data);
        const fdrSet = [...new Set(data.map(d => d.feeder_id))].sort();
        setFeeders(fdrSet);
        if (data.length)   setTarget(data[0].dt_id);
        if (fdrSet.length) setFeeder(fdrSet[0]);
      })
      .catch(() => addLog('⚠ Simulator not reachable (port 8081)'));
  }, []);

  const randomise = () => {
    if (!dts.length) return;
    const r = dts[Math.floor(Math.random() * dts.length)];
    setTarget(r.dt_id);
    addLog(`Randomised → ${r.dt_id}`);
  };

  const inject = async () => {
    if ((faultType === 'feeder_fault' && !feeder) || (faultType !== 'feeder_fault' && !target)) {
      addLog('⚠ Select a target before injecting a fault');
      return;
    }
    let url: string;
    let body: object;

    if (faultType === 'feeder_fault') {
      url  = `${SIM}/inject/feeder_fault`;
      body = { target_id: feeder };
    } else if (fastMode) {
      url  = `${SIM}/inject/fast_fault?fault_type=${faultType}`;
      body = { target_id: target };
    } else {
      url  = `${SIM}/inject/${faultType}`;
      body = { target_id: target };
    }

    try {
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const d = await r.json();
      if (!r.ok || d.status === 'error') throw new Error(d.detail ?? d.message ?? `Request failed (${r.status})`);
      addLog(`✓ Injected ${faultType}: ${JSON.stringify(d)}`);
    } catch (e) {
      addLog(`✗ ${e}`);
    }
  };

  const injectDeadSensor = async () => {
    if (!target) { addLog('⚠ Select a target DT first'); return; }
    // First fetch the pole list, pick the mid-point pole
    try {
      const r = await fetch(`${SIM}/poles/${target}`);
      if (!r.ok) throw new Error(`Unable to load poles (${r.status})`);
      const poles: string[] = await r.json();
      if (poles.length < 3) { addLog('Need ≥ 3 poles'); return; }
      // Mid-network pole — its children are still live
      const mid = poles[Math.floor(poles.length / 2)];
      const res = await fetch(`${SIM}/inject/dead_sensor`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ target_id: mid }),
      });
      const d = await res.json();
      if (!res.ok || d.status === 'error') throw new Error(d.detail ?? `Request failed (${res.status})`);
      addLog(`🔇 Dead sensor on ${mid} — NO ticket should appear`);
      console.log(d);
    } catch (e) { addLog(`✗ ${e}`); }
  };

  const injectScheduledOutage = async () => {
    if (!target) { addLog('⚠ Select a target DT first'); return; }
    try {
      const r = await fetch(`${SIM}/inject/scheduled_outage`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ target_id: target }),
      });
      const d = await r.json();
      if (!r.ok || d.status === 'error') throw new Error(d.detail ?? `Request failed (${r.status})`);
      addLog(`📅 Scheduled outage set for ${target} — inject fault now and NO ticket should appear`);
      console.log(d);
    } catch (e) { addLog(`✗ ${e}`); }
  };

  const restore = async () => {
    if (!target) { addLog('⚠ Select a target DT first'); return; }
    try {
      const r   = await fetch(`${SIM}/restore/${target}`, { method: 'POST' });
      const d   = await r.json();
      if (!r.ok || d.status === 'error') throw new Error(d.detail ?? `Request failed (${r.status})`);
      addLog(`✅ Restored ${target}: ${d.count} devices set live`);
    } catch (e) { addLog(`✗ ${e}`); }
  };

  return (
    <div className="sim-inner">
      <div className="sim-section-title">Fault Injection</div>

      <div className="sim-group">
        <label>Fault type</label>
        <select value={faultType} onChange={e => setFaultType(e.target.value as typeof faultType)}>
          <option value="span_fault">Span fault (pole + downstream)</option>
          <option value="dt_fault">DT fault (whole transformer)</option>
          <option value="feeder_fault">Feeder fault (all DTs on feeder)</option>
        </select>
      </div>

      {faultType !== 'feeder_fault' ? (
        <div className="sim-group">
          <label>Target DT</label>
          <div className="sim-target-row">
            <select value={target} onChange={e => setTarget(e.target.value)}>
              {dts.map(d => (
                <option key={d.dt_id} value={d.dt_id}>
                  {d.dt_id} — {d.feeder_id} ({d.pole_count} poles)
                </option>
              ))}
            </select>
            <button className="btn btn-muted btn-sm" onClick={randomise} title="Pick random DT">🎲</button>
          </div>
        </div>
      ) : (
        <div className="sim-group">
          <label>Target feeder</label>
          <select value={feeder} onChange={e => setFeeder(e.target.value)}>
            {feeders.map(f => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
      )}

      <div className="sim-group">
        <label className="sim-check-label">
          <input type="checkbox" checked={fastMode} onChange={e => setFastMode(e.target.checked)} />
          Fast mode — skip 3-min debounce (demo only)
        </label>
      </div>

      <button className="btn btn-red sim-inject-btn" onClick={inject}>⚡ Inject Fault</button>

      <div className="sim-divider">Noise cases — must NOT produce tickets</div>

      <div className="noise-btns">
        <button
          className="btn btn-muted"
          onClick={injectDeadSensor}
          title="Sends dark signal for 1 pole only. Children stay live → dead sensor detection → no ticket."
        >
          🔇 Dead sensor
        </button>
        <button
          className="btn btn-muted"
          onClick={injectScheduledOutage}
          title="Marks DT under planned outage. Inject a fault after this and no ticket should appear."
        >
          📅 Sched. outage
        </button>
      </div>

      <div className="sim-divider">Restoration</div>

      <button className="btn btn-green sim-restore-btn" onClick={restore}>
        ✅ Restore {target || '…'}
      </button>

      {/* Activity log */}
      {log.length > 0 && (
        <div className="sim-log">
          {log.map((l, i) => <div key={i} className="sim-log-line">{l}</div>)}
        </div>
      )}
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────

export default function App() {
  const [tickets, setTickets]         = useState<Ticket[]>([]);
  const [allDts, setAllDts]           = useState<DtOverview[]>([]);
  const [selectedId, setSelectedId]   = useState<number | null>(null);
  const [actionErrors, setActionErrors] = useState<Record<number, string>>({});
  const [loading, setLoading]         = useState(true);
  const [loadError, setLoadError]     = useState<string | null>(null);

  // Poll tickets every 3 s
  const fetchTickets = useCallback(async () => {
    try {
      const res  = await fetch(`${API}/tickets/`);
      if (!res.ok) throw new Error(`Unable to load tickets (${res.status})`);
      const data = await res.json();
      setTickets(data);
      setLoadError(null);
    } catch (e) {
      console.error(e);
      setLoadError('Unable to reach the fault service. Retrying automatically…');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTickets();
    const id = setInterval(fetchTickets, 3000);
    return () => clearInterval(id);
  }, [fetchTickets]);

  // Fetch DT overview once (for map)
  useEffect(() => {
    fetch(`${API}/topology/`)
      .then(async r => {
        if (!r.ok) throw new Error(`Unable to load network overview (${r.status})`);
        return r.json();
      })
      .then(setAllDts)
      .catch(console.error);
  }, []);

  const handleAction = async (id: number, action: string) => {
    try {
      const res  = await fetch(`${API}/tickets/${id}/action`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ action }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === 'error') {
        setActionErrors(prev => ({ ...prev, [id]: data.message ?? data.detail ?? `Action failed (${res.status})` }));
      } else {
        setActionErrors(prev => { const n = { ...prev }; delete n[id]; return n; });
        fetchTickets();
      }
    } catch (e) {
      console.error(e);
      setActionErrors(prev => ({ ...prev, [id]: 'Unable to contact the fault service. Please try again.' }));
    }
  };

  const activeTickets = tickets.filter(t => !['verified', 'closed'].includes(t.status));
  const selectedTicket = tickets.find(t => t.id === selectedId) ?? null;

  return (
    <div className="app-layout">

      {/* ── Header ── */}
      <header className="app-header">
        <h1 className="header-title">⚡ Propel AI — Fault Control Room</h1>
        <div className={`header-stat ${activeTickets.length > 0 ? 'stat-alert' : 'stat-ok'}`}>
          {activeTickets.length > 0
            ? `🔴 ${activeTickets.length} ACTIVE FAULT${activeTickets.length !== 1 ? 'S' : ''}`
            : '🟢 ALL CLEAR'}
        </div>
      </header>

      {/* ── Ticket panel ── */}
      <aside className="ticket-panel">
        <div className="panel-hdr">
          <span className="panel-title">Active Tickets</span>
          {activeTickets.length > 0 && (
            <span className="ticket-count-badge">{activeTickets.length}</span>
          )}
        </div>

        <div className="ticket-list">
          {loadError && <p className="list-error" role="alert">{loadError}</p>}
          {loading ? (
            <p className="list-empty">Loading…</p>
          ) : tickets.length === 0 ? (
            <p className="list-empty">No faults. All clear.</p>
          ) : (
            tickets.map(t => (
              <TicketCard
                key={t.id}
                ticket={t}
                isSelected={selectedId === t.id}
                onSelect={() => setSelectedId(prev => prev === t.id ? null : t.id)}
                onAction={action => handleAction(t.id, action)}
                actionError={actionErrors[t.id] ?? null}
              />
            ))
          )}
        </div>
      </aside>

      {/* ── Map panel ── */}
      <main className="map-panel">
        {!selectedTicket && (
          <div className="map-hint">
            Select a ticket to see its pole topology
          </div>
        )}
        <div className="map-legend">
          <span className="leg live">● Live</span>
          <span className="leg dark">● Dark</span>
          <span className="leg unknown">● Unknown</span>
          <span className="leg dt-dot">● DT</span>
          <span className="leg fault-line">— Fault span</span>
        </div>
        <MapView
          selectedTicket={selectedTicket}
          allDts={allDts}
          activeTickets={activeTickets}
          apiUrl={API}
        />
      </main>

      {/* ── Simulator panel ── */}
      <aside className="sim-panel">
        <div className="panel-hdr">
          <span className="panel-title">Network Simulator</span>
        </div>
        <SimulatorPanel />
      </aside>

    </div>
  );
}
