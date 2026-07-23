/**
 * AgentArchitecture — H-TRACE Neurosymbolic Flow Visualiser
 *
 * Renders the three H-TRACE tiers as a vertical flow:
 *   AI (Smart Manager · Gemini, non-real-time)
 *     → ML Local Teams (Isolation Forest "SPOT" + LSTM "PREDICT" + child "DECIDE")
 *       → Symbolic Safety Gate (deterministic rules, NOT AI)
 *         → Network Equipment → Outcome
 * Includes a Baseline/Live toggle and a live agent communication log.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box, Paper, Typography, Chip, IconButton,
  LinearProgress,
} from '@mui/material';
import HubIcon              from '@mui/icons-material/Hub';
import AccountTreeIcon      from '@mui/icons-material/AccountTree';
import RadarIcon            from '@mui/icons-material/Radar';
import TrendingUpIcon       from '@mui/icons-material/TrendingUp';
import GavelIcon            from '@mui/icons-material/Gavel';
import ShieldIcon           from '@mui/icons-material/Shield';
import ElectricBoltIcon     from '@mui/icons-material/ElectricBolt';
import SchoolIcon           from '@mui/icons-material/School';
import CheckCircleIcon      from '@mui/icons-material/CheckCircle';
import ErrorIcon            from '@mui/icons-material/Error';
import SyncIcon             from '@mui/icons-material/Sync';
import SignalCellularAltIcon from '@mui/icons-material/SignalCellularAlt';
import ActivityIcon         from '@mui/icons-material/GraphicEq';
import ChatIcon             from '@mui/icons-material/Chat';
import NightlightIcon       from '@mui/icons-material/Nightlight';
import CelebrationIcon      from '@mui/icons-material/Celebration';
import HealingIcon          from '@mui/icons-material/Healing';
import NetworkCheckIcon     from '@mui/icons-material/NetworkCheck';
import ExpandMoreIcon       from '@mui/icons-material/ExpandMore';
import EmojiObjectsIcon     from '@mui/icons-material/EmojiObjects';

// ─── Agent Definitions ────────────────────────────────────────────────────────

const AGENTS = {
  trigger:      { id: 'trigger',      label: 'KPI Telemetry',     sublabel: 'Equipment · Zenodo r1–r14',     icon: SignalCellularAltIcon, type: 'endpoint',     tools: [] },
  smart_manager:{ id: 'smart_manager',label: 'Smart Manager',     sublabel: 'AI · Gemini intent (non-RT)',   icon: HubIcon,               type: 'orchestrator', tools: ['ClassifyIntent','AssignAreaGoals','SuperviseHealing'] },
  anomaly:      { id: 'anomaly',      label: 'Anomaly Detector',  sublabel: 'ML · Isolation Forest (SPOT)',  icon: RadarIcon,             type: 'edge',         tools: ['ScoreKPI','SpotFault','FlagAnomaly'],          parallel: true },
  forecast:     { id: 'forecast',     label: 'Traffic Predictor', sublabel: 'ML · LSTM forecast (PREDICT)',  icon: TrendingUpIcon,        type: 'edge',         tools: ['PredictLoad','SleepWindow','PeakAhead'],       parallel: true },
  decision:     { id: 'decision',     label: 'Local Decision',    sublabel: 'ML child agent (DECIDE)',       icon: GavelIcon,             type: 'decision',     tools: ['ChooseAction','BuildCommand'] },
  safety_gate:  { id: 'safety_gate',  label: 'Safety Gate',       sublabel: 'Deterministic rules · NOT AI',  icon: ShieldIcon,            type: 'safety',       tools: ['CheckSleepLoad','BoundPower','LimitOffload','BlockOnFault'] },
  action:       { id: 'action',       label: 'Network Equipment', sublabel: 'Cell towers · TRX / antennas',  icon: ElectricBoltIcon,      type: 'edge',         tools: ['SetTRXPower','AdjustHandover','RestartCell'] },
  result:       { id: 'result',       label: 'Outcome',           sublabel: 'kWh / CBP / MTTD+MTTR',         icon: EmojiObjectsIcon,      type: 'endpoint',     tools: [] },
};

const FLOW_ROWS = [
  { nodes: ['trigger'],            label: null,                   divider: null },
  { nodes: ['smart_manager'],      label: 'AI · NON-REAL-TIME',   divider: 'amber' },
  { nodes: ['anomaly','forecast'], label: 'ML LOCAL TEAMS',       divider: 'amber' },
  { nodes: ['decision'],           label: null,                   divider: null },
  { nodes: ['safety_gate'],        label: 'SYMBOLIC SAFETY GATE', divider: 'red' },
  { nodes: ['action'],             label: null,                   divider: null },
  { nodes: ['result'],             label: null,                   divider: null },
];

const PIPELINES = {
  baseline:     ['trigger','smart_manager','anomaly'],
  night_mode:   ['trigger','smart_manager','forecast','decision','safety_gate','action','result'],
  festival_mode:['trigger','smart_manager','anomaly','forecast','decision','safety_gate','action','result'],
  self_healing: ['trigger','smart_manager','anomaly','decision','safety_gate','action','result'],
};

const COMM_MSGS = {
  night_mode: {
    trigger:      { to: 'Smart Manager',     msg: 'Low-traffic pattern on r3, r7, r12 — load <20% of capacity' },
    smart_manager:{ to: 'ML Local Teams',    msg: 'intent=save_energy → goal: schedule TRX sleep 02:00–05:00 (Area A/B)' },
    forecast:     { to: 'Local Decision',    msg: 'LSTM: load stays <30% until 04:45 — TRX-7 on r3 eligible to sleep' },
    decision:     { to: 'Safety Gate',       msg: 'PROPOSE sleep_cell(site=r3, trx=7, predicted_load=118)' },
    safety_gate:  { to: 'Network Equipment', msg: '✓ PASS — predicted_load 118 < 300 threshold · sleep approved' },
    action:       { to: 'Outcome',           msg: 'sleep_cell EXECUTED — 31.2% kWh reduction on r3' },
    result:       { to: '—',                 msg: 'RESULT: 31.2% kWh saved · 7 TRX asleep · coverage SLA held ✓' },
  },
  festival_mode: {
    trigger:      { to: 'Smart Manager',     msg: 'Surge — traffic 500% above baseline on r1, r4, r9' },
    smart_manager:{ to: 'ML Local Teams',    msg: 'intent=max_capacity → goal: protect QoS, keep cells awake' },
    anomaly:      { to: 'Traffic Predictor', msg: 'Isolation Forest: congestion anomaly score 0.91 on r1, r4, r9' },
    forecast:     { to: 'Local Decision',    msg: 'LSTM: peak load in T+8min — pre-emptively offload 35%' },
    decision:     { to: 'Safety Gate',       msg: 'PROPOSE offload(site=r1→neighbour, fraction=0.35)' },
    safety_gate:  { to: 'Network Equipment', msg: '✓ PASS — neighbour stays <80% capacity · offload approved' },
    action:       { to: 'Outcome',           msg: 'offload EXECUTED — CBP 8.2% → 1.1%' },
    result:       { to: '—',                 msg: 'RESULT: CBP 1.1% (was 8.2%) · avg delay 12ms · QoS held ✓' },
  },
  self_healing: {
    trigger:      { to: 'Smart Manager',     msg: 'Sleeping cell — r12 KPI=0 for 8+ consecutive samples' },
    smart_manager:{ to: 'ML Local Teams',    msg: 'intent=heal → goal: isolate & restore r12' },
    anomaly:      { to: 'Local Decision',    msg: 'Isolation Forest: fault CONFIRMED on r12 · MTTD 42s' },
    decision:     { to: 'Safety Gate',       msg: 'PROPOSE restart(site=r12) — mitigation action' },
    safety_gate:  { to: 'Network Equipment', msg: '✓ PASS — restart is mitigation · optimisation blocked during fault' },
    action:       { to: 'Outcome',           msg: 'restart EXECUTED — r12 KPI restored · MTTR 98s' },
    result:       { to: '—',                 msg: 'RESULT: MTTD 42s · MTTR 98s · r12 fully restored ✓' },
  },
  baseline: {
    trigger:      { to: 'Smart Manager',     msg: 'Steady-state KPI stream — all 14 sites nominal' },
    smart_manager:{ to: 'ML Local Teams',    msg: 'No operator intent — monitor only, no action' },
    anomaly:      { to: 'Smart Manager',     msg: 'Isolation Forest: all sites in-distribution — no anomaly' },
  },
};

// Type → color tokens
const TYPE_TOKEN = {
  endpoint:    { grad: 'linear-gradient(135deg,#2563eb,#3b82f6)', glow: '#2563eb40', chip: '#eff6ff', chipBorder: '#bfdbfe', chipText: '#1d4ed8' },
  orchestrator:{ grad: 'linear-gradient(135deg,#7c3aed,#a855f7)', glow: '#7c3aed40', chip: '#f5f3ff', chipBorder: '#ddd6fe', chipText: '#6d28d9' },
  router:      { grad: 'linear-gradient(135deg,#0284c7,#38bdf8)', glow: '#0284c740', chip: '#f0f9ff', chipBorder: '#bae6fd', chipText: '#0369a1' },
  edge:        { grad: 'linear-gradient(135deg,#059669,#34d399)', glow: '#05966940', chip: '#f0fdf4', chipBorder: '#bbf7d0', chipText: '#047857' },
  decision:    { grad: 'linear-gradient(135deg,#d97706,#fbbf24)', glow: '#d9770640', chip: '#fffbeb', chipBorder: '#fde68a', chipText: '#b45309' },
  safety:      { grad: 'linear-gradient(135deg,#dc2626,#f87171)', glow: '#dc262640', chip: '#fef2f2', chipBorder: '#fecaca', chipText: '#b91c1c' },
};

function getStatusColors(status, type) {
  const tk = TYPE_TOKEN[type] || TYPE_TOKEN.edge;
  if (status === 'active')    return { iconBg: tk.grad, glow: tk.glow, labelColor: '#0f172a', subColor: '#64748b', opacity: 1 };
  if (status === 'completed') return { iconBg: 'linear-gradient(135deg,#059669,#10b981)', glow: '#05966930', labelColor: '#047857', subColor: '#6ee7b7', opacity: 1 };
  if (status === 'failed')    return { iconBg: 'linear-gradient(135deg,#dc2626,#ef4444)', glow: '#dc262630', labelColor: '#b91c1c', subColor: '#fca5a5', opacity: 1 };
  if (status === 'skipped')   return { iconBg: '#e2e8f0', glow: 'none', labelColor: '#cbd5e1', subColor: '#e2e8f0', opacity: 0.5 };
  return                               { iconBg: '#e2e8f0', glow: 'none', labelColor: '#94a3b8', subColor: '#cbd5e1', opacity: 1 };
}

// ─── Animated vertical connector ─────────────────────────────────────────────

function Connector({ status, slim }) {
  const isA  = status === 'active';
  const isDone = status === 'completed';
  const lineColor = isA ? '#2563eb' : isDone ? '#059669' : status === 'failed' ? '#dc2626' : '#e2e8f0';

  return (
    <Box sx={{ pl: '19px', height: slim ? 8 : 16, flexShrink: 0, position: 'relative' }}>
      <Box sx={{
        width: 2, height: '100%',
        background: isA
          ? `linear-gradient(to bottom, ${lineColor}, ${lineColor}88)`
          : lineColor,
        borderRadius: 1,
        position: 'relative', overflow: 'hidden',
        transition: 'background 0.3s',
      }}>
        {isA && (
          <Box sx={{
            position: 'absolute', left: '50%', top: 0,
            transform: 'translateX(-50%)',
            width: 6, height: 6, borderRadius: '50%',
            bgcolor: lineColor,
            animation: 'flow-dot 0.9s ease-in-out infinite',
          }} />
        )}
      </Box>
    </Box>
  );
}

// ─── Agent node card ─────────────────────────────────────────────────────────

function NodeCard({ agent, status, isSelected, nodeRef, onClick, compact }) {
  const Icon = agent.icon;
  const sc   = getStatusColors(status, agent.type);
  const isA  = status === 'active';
  const isDone  = status === 'completed';
  const isFail  = status === 'failed';
  const iconSz  = compact ? 16 : 18;
  const circleSz = compact ? 34 : 40;

  return (
    <Box
      ref={nodeRef}
      onClick={() => onClick(agent)}
      sx={{
        display: 'flex', alignItems: 'center', gap: 1.5,
        px: 1, py: compact ? 0.6 : 0.8,
        borderRadius: 2,
        cursor: 'pointer',
        opacity: sc.opacity,
        bgcolor: isSelected ? `${sc.iconBg}18` : 'transparent',
        transition: 'background 0.2s, opacity 0.3s',
        '&:hover': { bgcolor: isSelected ? `${sc.iconBg}22` : '#f8fafc' },
      }}
    >
      {/* Circular icon */}
      <Box sx={{ position: 'relative', flexShrink: 0 }}>
        {isA && (
          <Box sx={{
            position: 'absolute', inset: -4, borderRadius: '50%',
            border: '2px solid currentColor',
            color: '#2563eb',
            opacity: 0.5,
            animation: 'agent-pulse-ring 1.8s ease-in-out infinite',
          }} />
        )}
        <Box sx={{
          width: circleSz, height: circleSz,
          borderRadius: '50%',
          background: sc.iconBg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: isA || isDone ? `0 4px 14px ${sc.glow}` : 'none',
          transition: 'all 0.3s',
          position: 'relative', zIndex: 1,
        }}>
          {isA
            ? <SyncIcon className="agent-icon-spin" sx={{ fontSize: iconSz, color: '#fff' }} />
            : isFail
            ? <ErrorIcon sx={{ fontSize: iconSz, color: '#fff' }} />
            : <Icon sx={{ fontSize: iconSz, color: status === 'pending' || status === 'skipped' ? '#94a3b8' : '#fff' }} />
          }
        </Box>

        {/* Status dot */}
        <Box sx={{
          position: 'absolute', bottom: -1, right: -1,
          width: 9, height: 9, borderRadius: '50%',
          border: '1.5px solid white',
          bgcolor: isA ? '#2563eb' : isDone ? '#059669' : isFail ? '#dc2626' : '#e2e8f0',
          transition: 'background 0.3s',
        }}>
          {isA && (
            <Box className="agent-dot-ping" sx={{ position: 'absolute', inset: 0, borderRadius: '50%', bgcolor: '#2563eb' }} />
          )}
        </Box>
      </Box>

      {/* Labels */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{
          fontSize: compact ? '0.73rem' : '0.79rem',
          fontWeight: 700, lineHeight: 1.2,
          color: sc.labelColor,
          transition: 'color 0.3s',
        }}>
          {agent.label}
        </Typography>
        {!compact && (
          <Typography sx={{
            fontSize: '0.62rem', color: sc.subColor,
            lineHeight: 1.2, mt: 0.1,
            transition: 'color 0.3s',
          }}>
            {agent.sublabel}
          </Typography>
        )}
      </Box>

      {/* Status chip */}
      {(isA || isDone || isFail) && (
        <Chip
          label={isA ? 'Active' : isDone ? 'Done' : 'Failed'}
          size="small"
          sx={{
            height: 18, fontSize: '0.6rem', fontWeight: 700, flexShrink: 0,
            bgcolor: isA ? '#eff6ff' : isDone ? '#f0fdf4' : '#fef2f2',
            color: isA ? '#2563eb' : isDone ? '#059669' : '#dc2626',
            border: `1px solid ${isA ? '#bfdbfe' : isDone ? '#bbf7d0' : '#fecaca'}`,
          }}
        />
      )}
    </Box>
  );
}

// ─── Section divider label ────────────────────────────────────────────────────

function SectionLabel({ label, color }) {
  const [bg, text, border] = color === 'red'
    ? ['#fef2f2', '#b91c1c', '#fecaca']
    : ['#fffbeb', '#b45309', '#fde68a'];
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, pl: '19px', my: 0.5 }}>
      <Box sx={{ flex: 1, height: 1, bgcolor: border, borderRadius: 1 }} />
      <Typography sx={{
        fontSize: '0.56rem', fontWeight: 800, letterSpacing: '0.9px',
        color: text, px: 0.5, bgcolor: bg, borderRadius: 0.5, py: '1px',
      }}>
        {label}
      </Typography>
      <Box sx={{ flex: 1, height: 1, bgcolor: border, borderRadius: 1 }} />
    </Box>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AgentArchitecture({ activeScenario = 'baseline', isRunning = false }) {
  const [nodeStatuses,  setNodeStatuses]  = useState({});
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [pipelineStep,  setPipelineStep]  = useState(-1);
  const [commLog,       setCommLog]       = useState([]);
  const [showComms,     setShowComms]     = useState(true);
  const [viewMode,      setViewMode]      = useState('live'); // 'baseline' | 'live'
  const [demoScenario,  setDemoScenario]  = useState('night_mode'); // scenario shown by the idle auto-demo
  const progressRef = useRef(null);
  const nodeRefs    = useRef({});
  const commEndRef  = useRef(null);

  const getInitial = useCallback((scenario) => {
    const pipe = PIPELINES[scenario] || PIPELINES.baseline;
    const map  = {};
    Object.keys(AGENTS).forEach(id => { map[id] = pipe.includes(id) ? 'pending' : 'skipped'; });
    return map;
  }, []);

  useEffect(() => { commEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [commLog]);

  useEffect(() => {
    const activeId = Object.keys(nodeStatuses).find(id => nodeStatuses[id] === 'active');
    if (activeId && nodeRefs.current[activeId]) {
      nodeRefs.current[activeId].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [nodeStatuses]);

  const addComm = useCallback((scenario, agentId) => {
    const msgs  = COMM_MSGS[scenario] || COMM_MSGS.baseline;
    const entry = msgs[agentId];
    if (!entry) return;
    setCommLog(prev => [...prev.slice(-40), {
      id: Date.now() + Math.random(),
      from: AGENTS[agentId]?.label || agentId,
      to: entry.to,
      msg: entry.msg,
      ts: new Date().toLocaleTimeString('en-US', { hour12: false }),
      scenario,
    }]);
  }, []);

  const runProgression = useCallback((scenario) => {
    if (progressRef.current) clearInterval(progressRef.current);
    const pipe = PIPELINES[scenario] || PIPELINES.baseline;
    let step = 0;

    setNodeStatuses(getInitial(scenario));
    setCommLog([]);
    setPipelineStep(0);

    setNodeStatuses(prev => ({ ...prev, [pipe[0]]: 'active' }));
    addComm(scenario, pipe[0]);

    progressRef.current = setInterval(() => {
      step += 1;
      const cur  = pipe[step];
      const prev = pipe[step - 1];

      if (step >= pipe.length) {
        clearInterval(progressRef.current);
        setNodeStatuses(p => { const u = { ...p }; if (prev) u[prev] = 'completed'; return u; });
        setPipelineStep(pipe.length);
        return;
      }

      setNodeStatuses(p => {
        const u = { ...p };
        if (prev) u[prev] = 'completed';
        if (cur)  u[cur]  = 'active';
        return u;
      });
      setPipelineStep(step);
      addComm(scenario, cur);
    }, 2400);
  }, [getInitial, addComm]);

  const runBaseline = useCallback(() => {
    if (progressRef.current) clearInterval(progressRef.current);
    const basePipe = ['trigger','smart_manager','anomaly'];
    let step = 0;

    const initial = {};
    Object.keys(AGENTS).forEach(id => { initial[id] = 'pending'; });
    setNodeStatuses(initial);
    setCommLog([]);

    const tick = () => {
      const cur  = basePipe[step % basePipe.length];
      const prev = basePipe[(step - 1 + basePipe.length) % basePipe.length];
      setNodeStatuses(p => {
        const u = { ...p };
        Object.keys(AGENTS).forEach(id => { if (!basePipe.includes(id)) u[id] = 'pending'; });
        basePipe.forEach(id => { u[id] = 'pending'; });
        u[prev] = 'completed';
        u[cur]  = 'active';
        return u;
      });
      addComm('baseline', cur);
      step += 1;
    };

    tick();
    progressRef.current = setInterval(tick, 3000);
  }, [addComm]);

  // Idle "Live" view: continuously walk the FULL neurosymbolic pipeline of each
  // scenario in turn (Night → Festival → Self-Healing) and loop, so every tier
  // — AI Smart Manager → ML Local Teams → Safety Gate → Equipment → Outcome —
  // visibly animates instead of sitting grey. This is the default demo flow.
  const runDemoLoop = useCallback(() => {
    if (progressRef.current) clearInterval(progressRef.current);
    const DEMO_SCENARIOS = ['night_mode', 'festival_mode', 'self_healing'];

    // Flatten into one looping plan; `null` nodes are short holds between runs.
    const steps = [];
    DEMO_SCENARIOS.forEach(scen => {
      PIPELINES[scen].forEach(node => steps.push({ scen, node }));
      steps.push({ scen, node: null });
      steps.push({ scen, node: null });
    });

    let k = 0;
    const tick = () => {
      const step = steps[k % steps.length];
      k += 1;
      if (!step || step.node === null) return;   // hold the completed diagram a beat

      const { scen, node } = step;
      setDemoScenario(scen);
      const pipe = PIPELINES[scen];
      const idx  = pipe.indexOf(node);
      setNodeStatuses(() => {
        const map = getInitial(scen);
        for (let j = 0; j < idx; j++) map[pipe[j]] = 'completed';
        map[node] = 'active';
        return map;
      });
      setPipelineStep(idx);
      addComm(scen, node);
    };

    tick();
    progressRef.current = setInterval(tick, 1700);
  }, [getInitial, addComm]);

  useEffect(() => {
    if (viewMode === 'baseline') {
      runBaseline();
    } else if (activeScenario !== 'baseline' && isRunning) {
      runProgression(activeScenario);
    } else {
      runDemoLoop();
    }
    return () => { if (progressRef.current) clearInterval(progressRef.current); };
  }, [activeScenario, isRunning, viewMode, runProgression, runBaseline, runDemoLoop]);

  // Which scenario is on screen right now: an explicit baseline, a live chat
  // scenario, or (when idle) the auto-demo's current scenario.
  const shownScenario =
    viewMode === 'baseline'                        ? 'baseline'
    : (activeScenario !== 'baseline' && isRunning) ? activeScenario
    : demoScenario;
  const pipe      = PIPELINES[shownScenario] || PIPELINES.baseline;
  const doneCount = pipe.filter(id => nodeStatuses[id] === 'completed').length;
  const isActive  = Object.values(nodeStatuses).some(s => s === 'active');
  const progress  = pipe.length > 0 ? (doneCount / pipe.length) * 100 : 0;

  const SCENARIO_META = {
    baseline:     { label: 'Baseline',   icon: <NetworkCheckIcon sx={{ fontSize: 11, color: '#2563eb' }} />, color: '#2563eb' },
    night_mode:   { label: 'Scenario A', icon: <NightlightIcon   sx={{ fontSize: 11, color: '#059669' }} />, color: '#059669' },
    festival_mode:{ label: 'Scenario B', icon: <CelebrationIcon  sx={{ fontSize: 11, color: '#d97706' }} />, color: '#d97706' },
    self_healing: { label: 'Scenario C', icon: <HealingIcon      sx={{ fontSize: 11, color: '#dc2626' }} />, color: '#dc2626' },
  };
  const sm = SCENARIO_META[shownScenario] || SCENARIO_META.baseline;

  const connStatus = (rowIdx) => {
    if (rowIdx >= FLOW_ROWS.length - 1) return 'pending';
    const curStatuses  = FLOW_ROWS[rowIdx].nodes.map(id => nodeStatuses[id] || 'pending');
    const nextStatuses = FLOW_ROWS[rowIdx + 1].nodes.map(id => nodeStatuses[id] || 'pending');
    if (nextStatuses.some(s => s === 'active'))                                         return 'active';
    if (curStatuses.every(s => s === 'completed') && nextStatuses.some(s => s !== 'pending')) return 'completed';
    if (curStatuses.some(s => s === 'failed'))                                          return 'failed';
    return 'pending';
  };

  return (
    <Paper elevation={0} sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', border: '1px solid #e8edf3' }}>

      {/* ── Header ── */}
      <Box sx={{ px: 2, py: 1.25, borderBottom: '1px solid #e8edf3', bgcolor: '#f8fafc', flexShrink: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.75 }}>
          {/* Title */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{
              width: 28, height: 28, borderRadius: 1.5,
              background: 'linear-gradient(135deg,#2563eb,#7c3aed)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(37,99,235,0.22)',
            }}>
              <ActivityIcon sx={{ color: 'white', fontSize: 15 }} />
            </Box>
            <Box>
              <Typography sx={{ fontWeight: 700, fontSize: '0.8rem', color: '#0f172a', lineHeight: 1 }}>
                H-TRACE Architecture
              </Typography>
              <Typography sx={{ fontSize: '0.61rem', color: '#94a3b8', mt: 0.1 }}>
                {isActive
                  ? `Processing… ${doneCount}/${pipe.length}`
                  : doneCount > 0 && doneCount === pipe.length
                  ? `${doneCount}/${pipe.length} completed`
                  : 'Monitoring'}
              </Typography>
            </Box>
          </Box>

          {/* Baseline / Live toggle — matches reference image */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {isActive && (
              <Chip label="Live" size="small" sx={{
                height: 18, fontSize: '0.6rem', fontWeight: 700,
                bgcolor: '#f0fdf4', border: '1px solid #bbf7d0', color: '#047857',
              }} />
            )}
            <Box sx={{ display: 'flex', border: '1px solid #e2e8f0', borderRadius: 1.5, overflow: 'hidden' }}>
              {['baseline','live'].map(mode => (
                <Box
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  sx={{
                    px: 1.25, py: 0.35, cursor: 'pointer',
                    fontSize: '0.6rem', fontWeight: 700, textTransform: 'capitalize',
                    bgcolor: viewMode === mode ? '#0f172a' : 'transparent',
                    color: viewMode === mode ? '#fff' : '#64748b',
                    transition: 'all 0.15s',
                    '&:hover': { bgcolor: viewMode === mode ? '#0f172a' : '#f1f5f9' },
                  }}
                >
                  {mode === 'baseline' ? '⚡ Baseline' : '● Live'}
                </Box>
              ))}
            </Box>
          </Box>
        </Box>

        {/* Scenario badge + progress */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mr: 0.5 }}>
            {sm.icon}
            <Typography sx={{ fontSize: '0.63rem', color: sm.color, fontWeight: 600 }}>{sm.label}</Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{
              flex: 1, height: 3, borderRadius: 2,
              bgcolor: '#f1f5f9',
              '& .MuiLinearProgress-bar': { bgcolor: sm.color, borderRadius: 2 },
            }}
          />
          <Typography sx={{ fontSize: '0.58rem', color: '#94a3b8', ml: 0.5 }}>
            {Math.round(progress)}%
          </Typography>
        </Box>
      </Box>

      {/* ── Flow diagram ── */}
      <Box sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', px: 1.5, pt: 1.5, pb: 1 }}>
        {FLOW_ROWS.map((row, rowIdx) => {
          const isParallel = row.nodes.length > 1;
          const isLast     = rowIdx === FLOW_ROWS.length - 1;
          const cs         = connStatus(rowIdx);

          return (
            <Box key={rowIdx}>
              {/* Section label */}
              {row.label && (
                <SectionLabel label={row.label} color={row.divider} />
              )}

              {/* Node(s) */}
              {isParallel ? (
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  {row.nodes.map(nodeId => (
                    <Box key={nodeId} sx={{ flex: 1 }} ref={el => { nodeRefs.current[nodeId] = el; }}>
                      <NodeCard
                        agent={AGENTS[nodeId]}
                        status={nodeStatuses[nodeId] || 'pending'}
                        isSelected={selectedAgent?.id === nodeId}
                        onClick={setSelectedAgent}
                        compact
                      />
                    </Box>
                  ))}
                </Box>
              ) : (
                row.nodes.map(nodeId => (
                  <Box key={nodeId} ref={el => { nodeRefs.current[nodeId] = el; }}>
                    <NodeCard
                      agent={AGENTS[nodeId]}
                      status={nodeStatuses[nodeId] || 'pending'}
                      isSelected={selectedAgent?.id === nodeId}
                      onClick={setSelectedAgent}
                    />
                  </Box>
                ))
              )}

              {/* Connector to next row */}
              {!isLast && <Connector status={cs} slim={isParallel || FLOW_ROWS[rowIdx + 1]?.nodes.length > 1} />}
            </Box>
          );
        })}
      </Box>

      {/* ── Selected agent detail ── */}
      {selectedAgent && (
        <Box sx={{ borderTop: '1px solid #e8edf3', bgcolor: '#fafbfc', flexShrink: 0, px: 2, py: 1.25 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 0.5 }}>
            <Box>
              <Typography sx={{ fontSize: '0.76rem', fontWeight: 700, color: '#0f172a' }}>{selectedAgent.label}</Typography>
              <Typography sx={{ fontSize: '0.62rem', color: '#94a3b8' }}>{selectedAgent.sublabel}</Typography>
            </Box>
            <IconButton size="small" onClick={() => setSelectedAgent(null)} sx={{ color: '#94a3b8', fontSize: '0.7rem' }}>✕</IconButton>
          </Box>
          <Typography sx={{ fontSize: '0.69rem', color: '#475569', lineHeight: 1.6, mb: 0.75 }}>
            {selectedAgent.id === 'trigger'      && 'Live KPI telemetry from 14 operator sites (r1–r14), streamed from the Zenodo dataset (DOI: 10.5281/zenodo.8147768). This is the equipment feedback loop into the ML tier.'}
            {selectedAgent.id === 'smart_manager'&& 'The AI tier (Gemini). Reads the operator\'s plain-language request and picks ONE high-level intent (save_energy / max_capacity / heal). Deliberately kept OUT of the real-time loop — it never issues a raw command, so control-loop hallucination stays 0%.'}
            {selectedAgent.id === 'anomaly'      && 'ML "SPOT a fault": an unsupervised Isolation Forest scores every KPI sample. Non-generative, so it cannot hallucinate. Drives Festival Mode (RQ2) congestion detection and Self-Healing (RQ3) fault detection.'}
            {selectedAgent.id === 'forecast'     && 'ML "PREDICT how busy soon": an LSTM forecasts near-future load (~1h ahead). Sets TRX sleep windows for Night Mode (RQ1) and pre-empts peaks for Festival Mode (RQ2).'}
            {selectedAgent.id === 'decision'     && 'The ML Local-Team child agent "DECIDE": turns the anomaly + forecast outputs into one structured, in-bounds action proposal. Real-time and deterministic — no LLM in this path.'}
            {selectedAgent.id === 'safety_gate'  && 'The symbolic half of the neurosymbolic design — deterministic rules, NOT AI. It boundary-checks every proposed action (sleep only if predicted load < 300/1000, power 0–100%, offload ≤ 80% neighbour capacity, mitigation-only during an active fault), giving a formal 0% false-pass guarantee — an architectural alternative to Habib et al.\'s learned, probabilistic safety classifier.'}
            {selectedAgent.id === 'action'       && 'Only Safety-Gate-approved commands reach the equipment: SetTRXPower (Night/RQ1), AdjustHandover / offload (Festival/RQ2), restart / reroute (Self-Healing/RQ3).'}
            {selectedAgent.id === 'result'       && 'Scenario outcome metrics, evaluated over 474 episodes: % kWh saved (RQ1) · Call Blocking Probability % (RQ2) · MTTD + MTTR in seconds (RQ3).'}
          </Typography>
          {selectedAgent.tools.length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.4 }}>
              {selectedAgent.tools.map(t => (
                <Chip key={t} label={t} size="small" sx={{
                  height: 16, fontSize: '0.57rem', fontFamily: 'monospace',
                  bgcolor: '#f0f9ff', color: '#0284c7', border: '1px solid #bae6fd',
                }} />
              ))}
            </Box>
          )}
        </Box>
      )}

      {/* ── Communication Log ── */}
      <Box sx={{ borderTop: '1px solid #e8edf3', flexShrink: 0 }}>
        <Box
          onClick={() => setShowComms(p => !p)}
          sx={{
            px: 2, py: 0.7, display: 'flex', alignItems: 'center', gap: 1,
            cursor: 'pointer', bgcolor: '#f8fafc',
            '&:hover': { bgcolor: '#f1f5f9' },
          }}
        >
          <ChatIcon sx={{ fontSize: 12, color: '#94a3b8' }} />
          <Typography sx={{ fontSize: '0.67rem', fontWeight: 600, color: '#64748b', flex: 1 }}>
            Agent Communication Log {commLog.length > 0 && `(${commLog.length})`}
          </Typography>
          <ExpandMoreIcon sx={{
            fontSize: 14, color: '#94a3b8',
            transform: showComms ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.2s',
          }} />
        </Box>

        {showComms && (
          <Box sx={{ maxHeight: 128, overflowY: 'auto', bgcolor: '#0f172a', px: 1.5, py: 1 }}>
            {commLog.length === 0 ? (
              <Typography sx={{ fontSize: '0.61rem', color: '#475569', fontFamily: 'monospace' }}>
                Waiting for scenario to start…
              </Typography>
            ) : (
              commLog.map((entry, i) => (
                <Box key={entry.id} sx={{ mb: 0.5, animation: i === commLog.length - 1 ? 'node-entrance 0.3s ease' : 'none' }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75 }}>
                    <Typography sx={{ fontSize: '0.56rem', color: '#475569', fontFamily: 'monospace', flexShrink: 0, mt: '1px' }}>
                      {entry.ts}
                    </Typography>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography sx={{ fontSize: '0.61rem', fontFamily: 'monospace', lineHeight: 1.3 }}>
                        <Box component="span" sx={{ color: '#60a5fa', fontWeight: 700 }}>{entry.from}</Box>
                        {entry.to !== '—' && (
                          <>
                            <Box component="span" sx={{ color: '#475569' }}> → </Box>
                            <Box component="span" sx={{ color: '#a78bfa' }}>{entry.to}</Box>
                          </>
                        )}
                        <Box component="span" sx={{ color: '#94a3b8' }}>:</Box>
                      </Typography>
                      <Typography sx={{ fontSize: '0.61rem', fontFamily: 'monospace', color: '#e2e8f0', lineHeight: 1.4 }}>
                        {entry.msg}
                      </Typography>
                    </Box>
                  </Box>
                </Box>
              ))
            )}
            <div ref={commEndRef} />
          </Box>
        )}
      </Box>

      {/* ── Legend ── */}
      <Box sx={{
        px: 1.5, py: 0.6, borderTop: '1px solid #e8edf3', bgcolor: '#f8fafc',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0,
      }}>
        <Box sx={{ display: 'flex', gap: 1.25 }}>
          {[['#e2e8f0','Pending'],['#2563eb','Active'],['#059669','Done'],['#dc2626','Failed']].map(([c, l]) => (
            <Box key={l} sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: c }} />
              <Typography sx={{ fontSize: '0.57rem', color: '#94a3b8', fontWeight: 500 }}>{l}</Typography>
            </Box>
          ))}
        </Box>
        <Typography sx={{ fontSize: '0.56rem', color: '#cbd5e1' }}>Tap for details</Typography>
      </Box>
    </Paper>
  );
}
