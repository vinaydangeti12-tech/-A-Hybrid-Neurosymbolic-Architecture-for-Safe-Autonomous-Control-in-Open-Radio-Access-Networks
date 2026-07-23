import { useState, useRef, useEffect } from 'react';
import {
  Box, Typography, Paper, TextField, IconButton, CircularProgress,
  Chip, Avatar, Container, Grid, Button, Tooltip,
} from '@mui/material';
import SmartToyIcon     from '@mui/icons-material/SmartToy';
import SendIcon         from '@mui/icons-material/Send';
import PersonIcon       from '@mui/icons-material/Person';
import BoltIcon         from '@mui/icons-material/Bolt';
import NetworkCheckIcon from '@mui/icons-material/NetworkCheck';
import HealingIcon      from '@mui/icons-material/Healing';
import NightlightIcon   from '@mui/icons-material/Nightlight';
import CelebrationIcon  from '@mui/icons-material/Celebration';
import StorageIcon      from '@mui/icons-material/Storage';
import ShieldIcon       from '@mui/icons-material/Shield';
import AccountTreeIcon  from '@mui/icons-material/AccountTree';
import VisibilityIcon   from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import AgentArchitecture from './AgentArchitecture';

// Relative by default so the Vite dev proxy (/api) is used and the app isn't
// pinned to localhost in a deployment. Override with VITE_API_URL if needed.
const API_BASE = import.meta.env.VITE_API_URL || '';

const SUGGESTIONS = [
  { icon: <NightlightIcon sx={{ fontSize: 14 }} />,    text: 'RQ1 · Night Mode: how much energy does the Smart Manager save by sleeping TRX units 02:00–05:00 on r1–r14?',     color: '#059669' },
  { icon: <CelebrationIcon sx={{ fontSize: 14 }} />,   text: 'RQ2 · Festival Mode: simulate a 500% surge — how does the LSTM pre-empt congestion and cut CBP?',                 color: '#d97706' },
  { icon: <HealingIcon sx={{ fontSize: 14 }} />,       text: 'RQ3 · Self-Healing: inject a sleeping-cell fault on r12 and report MTTD + MTTR',                                 color: '#dc2626' },
  { icon: <ShieldIcon sx={{ fontSize: 14 }} />,        text: 'Show the deterministic Safety Gate blocking an unsafe action (e.g. trying to sleep a busy cell)',                color: '#7c3aed' },
  { icon: <StorageIcon sx={{ fontSize: 14 }} />,       text: 'Summarise the 15 labelled anomaly windows in the Zenodo r1–r14 real KPI dataset (DOI:10.5281/zenodo.8147768)',  color: '#0284c7' },
  { icon: <NetworkCheckIcon sx={{ fontSize: 14 }} />,  text: 'Why is H-TRACE neurosymbolic? How does keeping the AI out of the real-time loop give 0% hallucination?',         color: '#2563eb' },
];

const WELCOME = `I am the **H-TRACE Smart Manager** — the AI tier of a *neurosymbolic* O-RAN control system.

**Why neurosymbolic?** H-TRACE splits the work so generative AI never touches the real-time loop:
• **AI · Smart Manager (me, Gemini):** I read your plain-language goal and pick ONE intent (save_energy / max_capacity / heal). I never issue a raw command → **0% control-loop hallucination**.
• **ML · Local Teams (Area A/B):** non-generative models run the real-time loop — an **Isolation Forest** SPOTs faults, an **LSTM** PREDICTs load, a child agent DECIDEs one in-bounds action.
• **Symbolic · Safety Gate:** deterministic rules (NOT AI) boundary-check every action → a formal **0% false-pass** guarantee, with **sub-100ms** decisions.

**Three scenarios I evaluate:**
• **RQ1 — Night Mode:** sleep TRX 02:00–05:00 → % kWh saved
• **RQ2 — Festival Mode:** 500% surge pre-empted → CBP ↓ and avg delay ms
• **RQ3 — Self-Healing:** auto-detect sleeping-cell faults → MTTD + MTTR

Evaluated over **474 episodes** (the 0% hallucination result carries a Rule-of-Three bound < 0.64% at 95% CI). The comparison with Habib et al. (2026) is *architectural* — a deterministic symbolic gate vs a learned probabilistic classifier — not a head-to-head number.

Ask me to run a scenario, explain a tier, show a blocked Safety-Gate action, or analyse the Zenodo r1–r14 dataset.`;

function inferScenario(text) {
  const t = text.toLowerCase();
  if (t.includes('night') || t.includes('energy') || t.includes('trx') || t.includes('sleep') || t.includes('kwh'))
    return 'night_mode';
  if (t.includes('festival') || t.includes('surge') || t.includes('congestion') || t.includes('cbp') || t.includes('traffic') || t.includes('load'))
    return 'festival_mode';
  if (t.includes('self-heal') || t.includes('heal') || t.includes('fault') || t.includes('mttd') || t.includes('mttr') || t.includes('anomaly') || t.includes('repair') || t.includes('tower_3') || t.includes('tower_'))
    return 'self_healing';
  return 'baseline';
}

function renderMarkdown(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code style="background:#f1f5f9;border:1px solid #e2e8f0;padding:2px 5px;border-radius:4px;font-family:monospace;font-size:0.84em">$1</code>')
    .replace(/\n/g, '<br/>');
}

function Message({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <Box sx={{ display: 'flex', gap: 1.5, flexDirection: isUser ? 'row-reverse' : 'row', mb: 2 }}>
      <Avatar sx={{
        width: 32, height: 32, flexShrink: 0,
        bgcolor: isUser ? '#eff6ff' : '#f5f3ff',
        border: `1px solid ${isUser ? '#bfdbfe' : '#ddd6fe'}`,
      }}>
        {isUser
          ? <PersonIcon sx={{ fontSize: 17, color: '#2563eb' }} />
          : <SmartToyIcon sx={{ fontSize: 17, color: '#7c3aed' }} />}
      </Avatar>
      <Box sx={{ maxWidth: '78%', display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start', gap: 0.5 }}>
        <Paper elevation={0} sx={{
          p: '10px 14px',
          bgcolor: isUser ? '#eff6ff' : '#ffffff',
          border: `1px solid ${isUser ? '#bfdbfe' : '#e8edf3'}`,
          borderRadius: isUser ? '12px 4px 12px 12px' : '4px 12px 12px 12px',
          boxShadow: '0 1px 3px rgba(15,23,42,0.05)',
        }}>
          <Typography variant="body2" sx={{ lineHeight: 1.75, color: '#1e293b', whiteSpace: 'pre-wrap' }}
            dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
          {msg.source && (
            <Chip label={msg.source} size="small"
              sx={{ mt: 1, height: 18, fontSize: '0.62rem', bgcolor: '#f8fafc', color: '#64748b', border: '1px solid #e8edf3' }} />
          )}
        </Paper>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.62rem', px: 0.5 }}>
          {new Date(msg.timestamp).toLocaleTimeString()}
        </Typography>
      </Box>
    </Box>
  );
}

const CHAT_STORAGE_KEY = 'htrace_chat_history';

function defaultMessages() {
  return [{ id: 0, role: 'assistant', content: WELCOME, timestamp: new Date().toISOString() }];
}

function loadStoredMessages() {
  try {
    const saved = sessionStorage.getItem(CHAT_STORAGE_KEY);
    const parsed = saved ? JSON.parse(saved) : null;
    if (Array.isArray(parsed) && parsed.length) return parsed;
  } catch { /* ignore corrupt / unavailable storage */ }
  return defaultMessages();
}

function ChatInterface() {
  // Persist the conversation across route changes (Dashboard ↔ Smart Manager)
  // for the tab session. Without this, navigating away unmounts the component
  // and wipes the chat; sessionStorage keeps it until the tab is closed.
  const [messages,     setMessages]     = useState(loadStoredMessages);
  const [input,        setInput]        = useState('');
  const [loading,      setLoading]      = useState(false);
  const [integStatus,  setIntegStatus]  = useState(null);
  const [chatScenario, setChatScenario] = useState('baseline');
  const [agentRunning, setAgentRunning] = useState(false);
  const [showAgentPanel, setShowAgentPanel] = useState(true);   // ← TOGGLE STATE
  const endRef    = useRef(null);
  const timerRef  = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  // Save on every change so the chat survives navigation away and back.
  useEffect(() => {
    try { sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages)); } catch { /* storage full / disabled */ }
  }, [messages]);
  useEffect(() => {
    fetch(`${API_BASE}/api/integration/status`).then(r => r.json()).then(setIntegStatus).catch(() => {});
  }, []);
  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  const send = async (text) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const inferred = inferScenario(trimmed);
    setChatScenario(inferred);
    setAgentRunning(true);
    setShowAgentPanel(true);

    setMessages(p => [...p, { id: Date.now(), role: 'user', content: trimmed, timestamp: new Date().toISOString() }]);
    setInput('');
    setLoading(true);

    // Sync backend scenario so telemetry stream also shows the right data
    if (inferred !== 'baseline') {
      fetch(`${API_BASE}/api/scenario/activate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: inferred }),
      }).catch(() => {});
    }

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed, context: 'trace_agent_page', scenario: inferred }),
      });
      const data = await res.json();
      setMessages(p => [...p, {
        id: Date.now() + 1, role: 'assistant',
        content: data.response || 'No response received.',
        source: data.source,
        timestamp: new Date().toISOString(),
      }]);
    } catch {
      setMessages(p => [...p, {
        id: Date.now() + 1, role: 'assistant',
        content: 'Connection error — is the backend server running on port 8000?',
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setLoading(false);
      // Keep architecture animated briefly, then reset to baseline
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        setAgentRunning(false);
        setChatScenario('baseline');
        fetch(`${API_BASE}/api/scenario/activate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scenario: 'baseline' }),
        }).catch(() => {});
      }, 22000);
    }
  };

  const modeLabel = { full_adk: 'Google ADK', gemini: 'Gemini AI', fallback: 'Fallback' }[integStatus?.mode] || 'Connecting…';
  const modeColor = integStatus?.mode === 'full_adk' ? 'success' : integStatus?.mode === 'gemini' ? 'warning' : 'default';

  return (
    <Box sx={{ bgcolor: 'background.default', minHeight: 'calc(100vh - 64px)' }}>
      <Container maxWidth="xl" sx={{ py: 3, height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>

        <Grid container spacing={3} sx={{ flex: 1, minHeight: 0 }}>

          {/* ── Left: Chat ── */}
          <Grid item xs={12} lg={showAgentPanel ? 8 : 12} sx={{ display: 'flex', flexDirection: 'column', height: '100%', transition: 'all 0.3s ease' }}>

            {/* Header */}
            <Paper elevation={0} sx={{ p: 2.5, mb: 2, borderRadius: 2, flexShrink: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{
                  width: 46, height: 46, borderRadius: 2, flexShrink: 0,
                  background: 'linear-gradient(135deg,#2563eb,#7c3aed)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: '0 3px 12px rgba(124,58,237,0.25)',
                }}>
                  <SmartToyIcon sx={{ color: 'white', fontSize: 24 }} />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="h6" sx={{ lineHeight: 1.2 }}>H-TRACE Smart Manager</Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mt: 0.4, flexWrap: 'wrap' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <Box className="status-online" />
                      <Typography variant="caption" color="text.secondary">Active</Typography>
                    </Box>
                    <Chip label={modeLabel} size="small" color={modeColor} sx={{ height: 18, fontSize: '0.68rem' }} />
                    <Chip icon={<ShieldIcon sx={{ fontSize: '12px !important' }} />} label="Safety Gate" size="small"
                      sx={{ height: 18, fontSize: '0.68rem', bgcolor: '#f0fdf4', color: '#047857', border: '1px solid #bbf7d0' }} />
                  </Box>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  <Box sx={{ textAlign: 'right', display: { xs: 'none', sm: 'block' } }}>
                    <Typography variant="caption" color="text.secondary" display="block">Dataset</Typography>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: '#2563eb' }}>Zenodo r1–r14</Typography>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.25 }}>Google ADK · Gemini</Typography>
                  </Box>
                  {/* ── Toggle button ── */}
                  <Tooltip title={showAgentPanel ? 'Hide Agent Monitor' : 'Show Agent Monitor'}>
                    <Button
                      variant={showAgentPanel ? 'contained' : 'outlined'}
                      disableElevation
                      size="small"
                      onClick={() => setShowAgentPanel(p => !p)}
                      startIcon={showAgentPanel
                        ? <VisibilityOffIcon sx={{ fontSize: 14 }} />
                        : <AccountTreeIcon sx={{ fontSize: 14 }} />}
                      sx={{
                        borderRadius: 2, fontSize: '0.72rem', fontWeight: 600,
                        whiteSpace: 'nowrap', flexShrink: 0,
                        ...(showAgentPanel
                          ? { bgcolor: '#0f172a', '&:hover': { bgcolor: '#1e293b' } }
                          : { borderColor: '#e2e8f0', color: '#64748b', '&:hover': { borderColor: '#2563eb', color: '#2563eb', bgcolor: '#eff6ff' } }),
                      }}
                    >
                      {showAgentPanel ? 'Hide Agents' : 'Show Agents'}
                    </Button>
                  </Tooltip>
                </Box>
              </Box>
            </Paper>

            {/* Messages */}
            <Paper elevation={0} sx={{ flex: 1, overflow: 'auto', p: 3, mb: 2, bgcolor: '#fafbfc', borderRadius: 2 }}>
              {messages.map(msg => <Message key={msg.id} msg={msg} />)}
              {loading && (
                <Box sx={{ display: 'flex', gap: 1.5, mb: 2 }}>
                  <Avatar sx={{ width: 32, height: 32, bgcolor: '#f5f3ff', border: '1px solid #ddd6fe', flexShrink: 0 }}>
                    <SmartToyIcon sx={{ fontSize: 17, color: '#7c3aed' }} />
                  </Avatar>
                  <Paper elevation={0} sx={{ p: '10px 14px', bgcolor: '#ffffff', border: '1px solid #e8edf3', borderRadius: '4px 12px 12px 12px', display: 'flex', gap: 1, alignItems: 'center' }}>
                    <CircularProgress size={13} sx={{ color: '#7c3aed' }} />
                    <Box>
                      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                        {{
                          night_mode:   'Smart Manager → LSTM Traffic Predictor — forecasting TRX sleep window…',
                          festival_mode:'Smart Manager → Isolation Forest — scoring congestion anomaly…',
                          self_healing: 'Smart Manager → Isolation Forest — confirming fault…',
                          baseline:     'Smart Manager processing…',
                        }[chatScenario] || 'Smart Manager processing…'}
                      </Typography>
                    </Box>
                  </Paper>
                </Box>
              )}
              <div ref={endRef} />
            </Paper>

            {/* Suggestions */}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 1.5, flexShrink: 0 }}>
              {SUGGESTIONS.map((s, i) => (
                <Chip
                  key={i}
                  icon={<Box sx={{ color: s.color, display: 'flex', ml: 0.5 }}>{s.icon}</Box>}
                  label={s.text.length > 44 ? s.text.slice(0, 44) + '…' : s.text}
                  size="small"
                  onClick={() => send(s.text)}
                  disabled={loading}
                  sx={{
                    cursor: 'pointer', bgcolor: '#ffffff', border: '1px solid #e8edf3', fontSize: '0.73rem',
                    '&:hover': { bgcolor: '#f8fafc', borderColor: s.color, boxShadow: `0 2px 8px ${s.color}18` },
                    transition: 'border-color 0.15s, box-shadow 0.15s',
                  }}
                />
              ))}
            </Box>

            {/* Input */}
            <Paper elevation={0} sx={{
              p: '8px 8px 8px 16px', display: 'flex', gap: 1, alignItems: 'flex-end',
              borderRadius: 2, flexShrink: 0,
              '&:focus-within': { borderColor: '#bfdbfe', boxShadow: '0 0 0 3px rgba(37,99,235,0.10)' },
              transition: 'border-color 0.15s, box-shadow 0.15s',
            }}>
              <TextField
                fullWidth multiline maxRows={4}
                placeholder="Ask the H-TRACE Smart Manager…"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); } }}
                disabled={loading}
                variant="standard"
                sx={{ '& .MuiInputBase-root': { '&:before': { display: 'none' }, '&:after': { display: 'none' }, fontSize: '0.9rem' } }}
              />
              <IconButton
                onClick={() => send(input)}
                disabled={loading || !input.trim()}
                sx={{
                  bgcolor: '#2563eb', color: 'white', borderRadius: 2, width: 40, height: 40, flexShrink: 0,
                  '&:hover': { bgcolor: '#1d4ed8' },
                  '&.Mui-disabled': { bgcolor: '#e8edf3', color: '#94a3b8' },
                }}
              >
                {loading ? <CircularProgress size={16} sx={{ color: 'white' }} /> : <SendIcon sx={{ fontSize: 18 }} />}
              </IconButton>
            </Paper>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.75, textAlign: 'center' }}>
              Enter to send · Shift+Enter for new line
            </Typography>
          </Grid>

          {/* ── Right: Agent Architecture ── */}
          {showAgentPanel && (
            <Grid item xs={12} lg={4} sx={{ height: '100%' }}>
              <AgentArchitecture
                activeScenario={chatScenario}
                isRunning={agentRunning || loading}
              />
            </Grid>
          )}

        </Grid>
      </Container>
    </Box>
  );
}

export default ChatInterface;
