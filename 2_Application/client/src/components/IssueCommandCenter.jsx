import { useState, useEffect, useRef } from 'react';
import {
  Box, Card, CardContent, Typography, Chip, Button, Grid, LinearProgress,
  IconButton, Tooltip, Snackbar, Alert, TextField, Drawer, Tabs, Tab,
  Avatar, CircularProgress, Paper, Divider,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import VisibilityIcon from '@mui/icons-material/Visibility';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import CellTowerIcon from '@mui/icons-material/CellTower';
import CloseIcon from '@mui/icons-material/Close';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ChatIcon from '@mui/icons-material/Chat';
import SendIcon from '@mui/icons-material/Send';
import PersonIcon from '@mui/icons-material/Person';
import TimelineIcon from '@mui/icons-material/Timeline';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import RefreshIcon from '@mui/icons-material/Refresh';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import ShieldIcon from '@mui/icons-material/Shield';

// Relative by default so the Vite dev proxy (/api) is used and the app isn't
// pinned to localhost in a deployment. Override with VITE_API_URL if needed.
const API_BASE = import.meta.env.VITE_API_URL || '';
const PIPELINE = ['Monitoring', 'Prediction', 'Decision xApp', 'Action', 'Learning'];

const AGENT_COLORS = {
  'Monitoring':    '#059669',
  'Prediction':    '#2563eb',
  'Decision xApp': '#d97706',
  'Action':        '#dc2626',
  'Learning':      '#7c3aed',
};

const severityConfig = {
  critical: { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', chipColor: 'error',   icon: ErrorIcon },
  high:     { color: '#d97706', bg: '#fffbeb', border: '#fde68a', chipColor: 'warning', icon: WarningIcon },
  medium:   { color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe', chipColor: 'info',    icon: undefined },
};

const getSeverityConf = s => severityConfig[(s || '').toLowerCase()] || severityConfig.medium;

function PipelineBar({ activeIdx }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
      {PIPELINE.map((a, i) => (
        <Box key={a} sx={{ display: 'flex', alignItems: 'center' }}>
          <Chip
            label={a}
            size="small"
            sx={{
              height: 18, fontSize: '0.62rem',
              fontWeight: activeIdx === i ? 700 : 400,
              bgcolor: activeIdx === i
                ? AGENT_COLORS[a]
                : activeIdx > i ? `${AGENT_COLORS[a]}18` : '#f8fafc',
              color: activeIdx === i
                ? '#fff'
                : activeIdx > i ? AGENT_COLORS[a] : '#94a3b8',
              border: `1px solid ${activeIdx >= i ? `${AGENT_COLORS[a]}60` : '#e8edf3'}`,
              transition: 'all 0.25s',
            }}
          />
          {i < PIPELINE.length - 1 && (
            <ArrowForwardIcon sx={{ fontSize: 9, mx: 0.25, color: activeIdx > i ? '#94a3b8' : '#e2e8f0' }} />
          )}
        </Box>
      ))}
    </Box>
  );
}

function renderMd(text) {
  return (text || '')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br/>');
}

function IssueCommandCenter({ issues, onIssueResolved }) {
  const [selectedIssue,    setSelectedIssue]    = useState(null);
  const [drawerOpen,       setDrawerOpen]        = useState(false);
  const [drawerTab,        setDrawerTab]         = useState(0);
  const [actionLoading,    setActionLoading]     = useState(null);
  const [snackbar,         setSnackbar]          = useState({ open: false, message: '', severity: 'success' });
  const [chatMessages,     setChatMessages]      = useState([]);
  const [chatInput,        setChatInput]         = useState('');
  const [chatLoading,      setChatLoading]       = useState(false);
  const [aiAnalysis,       setAiAnalysis]        = useState(null);
  const [analysisLoading,  setAnalysisLoading]   = useState(false);
  const [activeAgentIdx,   setActiveAgentIdx]    = useState(-1);
  const [agentLogs,        setAgentLogs]         = useState([]);
  const [remStep,          setRemStep]           = useState(-1);
  const chatEnd = useRef(null);

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages]);

  useEffect(() => {
    if (selectedIssue) {
      setChatMessages([{
        id: Date.now(), role: 'assistant',
        content: `Analysing **${selectedIssue.title}**. How can I help resolve this issue?\n\nAsk for root cause, remediation steps, or impact assessment.`,
        timestamp: new Date().toISOString(),
      }]);
      setAiAnalysis(null); setAgentLogs([]); setRemStep(-1); setActiveAgentIdx(-1);
    }
  }, [selectedIssue]);

  const simulatePipeline = async (issue) => {
    const logs = [];
    for (let i = 0; i < PIPELINE.length; i++) {
      setActiveAgentIdx(i);
      const log = { agent: PIPELINE[i], message: `${PIPELINE[i]} reviewed incident ${issue.id}`, timestamp: new Date().toISOString() };
      logs.push(log);
      setAgentLogs([...logs]);
      await new Promise(r => setTimeout(r, 600));
    }
    return logs;
  };

  const handleRemediate = async (issue) => {
    setActionLoading(issue.id);
    setAgentLogs([]); setRemStep(0); setActiveAgentIdx(-1);
    try {
      setRemStep(1); await simulatePipeline(issue);
      setRemStep(2);
      const res = await fetch(`${API_BASE}/api/remediation/trigger`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ issueId: issue.id, action: issue.suggestedAction || 'auto_remediate', region: 'region-IE-01' }),
      });
      const data = await res.json();
      setRemStep(3);
      await new Promise(r => setTimeout(r, 600));
      if (res.ok) {
        const src = data.source === 'principal_agent' ? 'ADK Agent' : data.source === 'gemini' ? 'Gemini AI' : 'System';
        setSnackbar({ open: true, message: `Resolved via ${src}`, severity: 'success' });
        setChatMessages(prev => [...prev, {
          id: Date.now(), role: 'assistant',
          content: `**Remediation Complete**\nAction: ${data.action || issue.suggestedAction}\nSource: ${src}${data.agent_response ? `\n\n${data.agent_response}` : ''}`,
          timestamp: new Date().toISOString(),
        }]);
        setTimeout(() => { onIssueResolved(issue.id); setActionLoading(null); setRemStep(-1); }, 1500);
      } else throw new Error(data.error || 'Failed');
    } catch (err) {
      setSnackbar({ open: true, message: err.message, severity: 'error' });
      setActionLoading(null); setRemStep(-1);
    }
  };

  const handleAnalyse = async (issue) => {
    setAnalysisLoading(true); setAiAnalysis(null);
    try {
      const res = await fetch(`${API_BASE}/api/issue/analyze`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ issueId: issue.id, issue, region: 'region-IE-01' }),
      });
      const data = await res.json();
      setAiAnalysis({
        content: data.analysis || `**${issue.title}** (${issue.severity?.toUpperCase()})\n\nAffected: ${issue.affectedTowers?.join(', ')}. Recommended: ${issue.suggestedAction}.`,
        source: data.source || 'fallback',
      });
    } catch {
      setAiAnalysis({ content: 'Analysis unavailable. Check backend connection.', source: 'error' });
    } finally { setAnalysisLoading(false); }
  };

  const handleSendChat = async () => {
    if (!chatInput.trim() || chatLoading || !selectedIssue) return;
    const msg = chatInput.trim();
    setChatMessages(prev => [...prev, { id: Date.now(), role: 'user', content: msg, timestamp: new Date().toISOString() }]);
    setChatInput('');
    setChatLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `Issue "${selectedIssue.title}" (${selectedIssue.severity}): ${msg}`, context: 'issue_resolution' }),
      });
      const data = await res.json();
      setChatMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', content: data.response || 'No response.', source: data.source, timestamp: new Date().toISOString() }]);
    } catch {
      setChatMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', content: 'Backend error.', timestamp: new Date().toISOString() }]);
    } finally { setChatLoading(false); }
  };

  const openDrawer  = (issue) => { setSelectedIssue(issue); setDrawerOpen(true); setDrawerTab(0); handleAnalyse(issue); };
  const closeDrawer = () => { setDrawerOpen(false); setSelectedIssue(null); setChatMessages([]); setAiAnalysis(null); setAgentLogs([]); };

  if (!issues.length) {
    return (
      <Box sx={{
        textAlign: 'center', py: 7,
        bgcolor: '#f0fdf4', borderRadius: 2,
        border: '1px solid #bbf7d0',
      }}>
        <CheckCircleIcon sx={{ fontSize: 44, color: '#059669', mb: 1.5 }} />
        <Typography variant="h6" sx={{ color: '#047857', fontWeight: 700, mb: 0.5 }}>
          All Systems Operational
        </Typography>
        <Typography variant="body2" color="text.secondary">
          No active issues — H-TRACE ML Local Teams monitoring continuously
        </Typography>
      </Box>
    );
  }

  return (
    <>
      <Grid container spacing={2}>
        {issues.map(issue => {
          const conf = getSeverityConf(issue.severity);
          const SeverityIcon = conf.icon;
          return (
            <Grid item xs={12} md={6} lg={4} key={issue.id}>
              <Card
                className="card-hover"
                sx={{
                  height: '100%', cursor: 'pointer',
                  borderLeft: `4px solid ${conf.color}`,
                }}
                onClick={() => openDrawer(issue)}
              >
                <CardContent sx={{ p: 2.5 }}>
                  {/* Top row */}
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                    <Chip
                      label={issue.severity?.toUpperCase() || 'MEDIUM'}
                      color={conf.chipColor}
                      size="small"
                      icon={SeverityIcon ? <SeverityIcon /> : undefined}
                      sx={{ fontWeight: 700, fontSize: '0.72rem' }}
                    />
                    <Chip
                      label={issue.status || 'Active'}
                      size="small" variant="outlined"
                      sx={{ fontSize: '0.72rem', color: '#64748b', borderColor: '#e2e8f0' }}
                    />
                  </Box>

                  {/* Title + description */}
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5, lineHeight: 1.3 }}>
                    {issue.title}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.75, lineHeight: 1.6 }}>
                    {issue.description}
                  </Typography>

                  {/* Meta */}
                  <Box sx={{ display: 'flex', gap: 2.5, mb: 1.75 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <CellTowerIcon sx={{ fontSize: 13, color: '#94a3b8' }} />
                      <Typography variant="caption" color="text.secondary">
                        {issue.affectedTowers?.length || 0} towers
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <Typography variant="caption" color="text.secondary">Impact:</Typography>
                      <Typography variant="caption" sx={{
                        fontWeight: 700,
                        color: issue.impactScore > 80 ? '#dc2626' : issue.impactScore > 50 ? '#d97706' : '#059669',
                      }}>
                        {issue.impactScore || 'N/A'}%
                      </Typography>
                    </Box>
                  </Box>

                  {/* Agent pipeline */}
                  <PipelineBar activeIdx={PIPELINE.indexOf(issue.activeAgent || '')} />

                  {actionLoading === issue.id && (
                    <LinearProgress sx={{ my: 1.5, height: 3 }} />
                  )}

                  {/* Action row */}
                  <Box sx={{ display: 'flex', gap: 1, mt: 2 }} onClick={e => e.stopPropagation()}>
                    <Button
                      variant="contained" size="small" disableElevation
                      startIcon={actionLoading === issue.id
                        ? <CircularProgress size={12} sx={{ color: 'inherit' }} />
                        : <AutoFixHighIcon sx={{ fontSize: 15 }} />}
                      disabled={actionLoading === issue.id}
                      onClick={e => { e.stopPropagation(); handleRemediate(issue); }}
                      sx={{ flex: 1, bgcolor: '#2563eb', '&:hover': { bgcolor: '#1d4ed8' } }}
                    >
                      {actionLoading === issue.id ? 'Processing…' : 'Auto Remediate'}
                    </Button>
                    <Tooltip title="Details & AI Chat">
                      <IconButton
                        size="small"
                        onClick={e => { e.stopPropagation(); openDrawer(issue); }}
                        sx={{
                          border: '1px solid #e8edf3',
                          '&:hover': { borderColor: '#2563eb', bgcolor: '#eff6ff' },
                        }}
                      >
                        <VisibilityIcon sx={{ fontSize: 16 }} />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>

      {/* ─── Side Drawer ─── */}
      <Drawer
        anchor="right" open={drawerOpen} onClose={closeDrawer}
        PaperProps={{ sx: { width: { xs: '100%', md: 580 }, bgcolor: '#ffffff' } }}
      >
        {selectedIssue && (
          <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Drawer header */}
            <Box sx={{ p: 3, borderBottom: '1px solid #e8edf3', bgcolor: '#f8fafc' }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
                <Box sx={{ flex: 1, pr: 1 }}>
                  <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                    <Chip label={selectedIssue.severity?.toUpperCase()} color={getSeverityConf(selectedIssue.severity).chipColor} size="small" sx={{ fontWeight: 700 }} />
                    <Chip label={selectedIssue.status} size="small" variant="outlined" sx={{ borderColor: '#e2e8f0', color: '#64748b' }} />
                  </Box>
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>{selectedIssue.title}</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{selectedIssue.description}</Typography>
                </Box>
                <IconButton onClick={closeDrawer} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
              </Box>
              <Box sx={{ display: 'flex', gap: 3 }}>
                {[['Towers', selectedIssue.affectedTowers?.length || 0], ['Impact', `${selectedIssue.impactScore || 'N/A'}%`], ['ID', selectedIssue.id]].map(([l, v]) => (
                  <Box key={l}>
                    <Typography variant="caption" color="text.secondary">{l}</Typography>
                    <Typography variant="body2" sx={{
                      fontWeight: 700, color: '#2563eb',
                      fontFamily: l === 'ID' ? 'monospace' : 'inherit',
                      fontSize: l === 'ID' ? '0.78rem' : undefined,
                    }}>{v}</Typography>
                  </Box>
                ))}
              </Box>
            </Box>

            <Tabs
              value={drawerTab}
              onChange={(_, v) => setDrawerTab(v)}
              sx={{ borderBottom: '1px solid #e8edf3', px: 2, '& .MuiTabs-indicator': { height: 2, bgcolor: '#2563eb' } }}
            >
              <Tab icon={<AnalyticsIcon sx={{ fontSize: 15 }} />} label="Analysis"   iconPosition="start" sx={{ fontSize: '0.82rem', minHeight: 48 }} />
              <Tab icon={<ChatIcon      sx={{ fontSize: 15 }} />} label="AI Chat"    iconPosition="start" sx={{ fontSize: '0.82rem', minHeight: 48 }} />
              <Tab icon={<TimelineIcon  sx={{ fontSize: 15 }} />} label="Agent Logs" iconPosition="start" sx={{ fontSize: '0.82rem', minHeight: 48 }} />
            </Tabs>

            <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
              {/* Tab 0 — Analysis */}
              {drawerTab === 0 && (
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                    <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      <SmartToyIcon sx={{ fontSize: 16, color: '#7c3aed' }} /> AI Analysis
                    </Typography>
                    <Button
                      size="small"
                      startIcon={analysisLoading ? <CircularProgress size={12} /> : <RefreshIcon sx={{ fontSize: 14 }} />}
                      disabled={analysisLoading}
                      onClick={() => handleAnalyse(selectedIssue)}
                      sx={{ color: '#2563eb', fontSize: '0.75rem' }}
                    >
                      Re-analyse
                    </Button>
                  </Box>
                  <Paper elevation={0} sx={{ p: 2, bgcolor: '#f8fafc', mb: 3, borderRadius: 2 }}>
                    {analysisLoading
                      ? <Box sx={{ py: 5, textAlign: 'center' }}><CircularProgress size={24} sx={{ color: '#7c3aed' }} /></Box>
                      : aiAnalysis
                      ? <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.75 }}
                          dangerouslySetInnerHTML={{ __html: renderMd(aiAnalysis.content) }} />
                      : <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center', fontSize: '0.875rem' }}>
                          Click Re-analyse to run AI analysis
                        </Typography>
                    }
                  </Paper>

                  {remStep >= 0 && (
                    <>
                      <Divider sx={{ mb: 2 }} />
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.75 }}>
                        <ShieldIcon sx={{ fontSize: 16, color: '#059669' }} />
                        <Typography variant="subtitle2">Remediation Progress</Typography>
                      </Box>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                        {['Analyse Issue', 'Agent Pipeline', 'Execute Action', 'Verification'].map((step, i) => (
                          <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, opacity: remStep >= i ? 1 : 0.3 }}>
                            <Box sx={{
                              width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              bgcolor: remStep > i ? '#f0fdf4' : remStep === i ? '#eff6ff' : '#f8fafc',
                              border: `2px solid ${remStep > i ? '#059669' : remStep === i ? '#2563eb' : '#e2e8f0'}`,
                            }}>
                              {remStep > i
                                ? <CheckCircleIcon sx={{ fontSize: 15, color: '#059669' }} />
                                : remStep === i
                                ? <CircularProgress size={13} sx={{ color: '#2563eb' }} />
                                : <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, color: '#94a3b8' }}>{i + 1}</Typography>}
                            </Box>
                            <Typography variant="body2" sx={{ fontWeight: remStep === i ? 600 : 400 }}>{step}</Typography>
                          </Box>
                        ))}
                      </Box>
                    </>
                  )}
                </Box>
              )}

              {/* Tab 1 — Chat */}
              {drawerTab === 1 && (
                <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <Box sx={{ flex: 1, overflow: 'auto', mb: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    {chatMessages.map(msg => (
                      <Box key={msg.id} sx={{ display: 'flex', gap: 1, flexDirection: msg.role === 'user' ? 'row-reverse' : 'row' }}>
                        <Avatar sx={{
                          width: 28, height: 28, flexShrink: 0,
                          bgcolor: msg.role === 'user' ? '#eff6ff' : '#f5f3ff',
                          border: `1px solid ${msg.role === 'user' ? '#bfdbfe' : '#ddd6fe'}`,
                        }}>
                          {msg.role === 'user'
                            ? <PersonIcon sx={{ fontSize: 14, color: '#2563eb' }} />
                            : <SmartToyIcon sx={{ fontSize: 14, color: '#7c3aed' }} />}
                        </Avatar>
                        <Paper elevation={0} sx={{
                          p: '8px 12px', maxWidth: '82%',
                          bgcolor: msg.role === 'user' ? '#eff6ff' : '#f8fafc',
                          border: `1px solid ${msg.role === 'user' ? '#bfdbfe' : '#e8edf3'}`,
                          borderRadius: msg.role === 'user' ? '10px 3px 10px 10px' : '3px 10px 10px 10px',
                        }}>
                          <Typography variant="caption" sx={{ lineHeight: 1.65 }}
                            dangerouslySetInnerHTML={{ __html: renderMd(msg.content) }} />
                        </Paper>
                      </Box>
                    ))}
                    {chatLoading && (
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Avatar sx={{ width: 28, height: 28, bgcolor: '#f5f3ff', border: '1px solid #ddd6fe', flexShrink: 0 }}>
                          <SmartToyIcon sx={{ fontSize: 14, color: '#7c3aed' }} />
                        </Avatar>
                        <Paper elevation={0} sx={{ p: '8px 12px', bgcolor: '#f8fafc', border: '1px solid #e8edf3', borderRadius: '3px 10px 10px 10px', display: 'flex', alignItems: 'center', gap: 1 }}>
                          <CircularProgress size={10} sx={{ color: '#7c3aed' }} />
                          <Typography sx={{ fontSize: '0.72rem', color: '#94a3b8' }}>Thinking…</Typography>
                        </Paper>
                      </Box>
                    )}
                    <div ref={chatEnd} />
                  </Box>
                  <Box sx={{ display: 'flex', gap: 1, pt: 1.5, borderTop: '1px solid #e8edf3' }}>
                    <TextField
                      fullWidth size="small" placeholder="Ask about this issue…"
                      value={chatInput}
                      onChange={e => setChatInput(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleSendChat()}
                      disabled={chatLoading}
                      sx={{ '& .MuiOutlinedInput-root': { bgcolor: '#f8fafc' } }}
                    />
                    <IconButton
                      onClick={handleSendChat}
                      disabled={chatLoading || !chatInput.trim()}
                      sx={{
                        bgcolor: '#2563eb', color: 'white', borderRadius: 1.5,
                        '&:hover': { bgcolor: '#1d4ed8' },
                        '&.Mui-disabled': { bgcolor: '#f1f5f9', color: '#94a3b8' },
                      }}
                    >
                      <SendIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                  </Box>
                </Box>
              )}

              {/* Tab 2 — Agent Logs */}
              {drawerTab === 2 && (
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 1.5 }}>Agent Pipeline</Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0.5, mb: 2.5 }}>
                    {PIPELINE.map((a, i) => (
                      <Box key={a} sx={{ display: 'flex', alignItems: 'center' }}>
                        <Chip label={a} size="small" sx={{
                          height: 20, fontSize: '0.7rem',
                          bgcolor: activeAgentIdx === i ? AGENT_COLORS[a] : activeAgentIdx > i ? `${AGENT_COLORS[a]}15` : '#f8fafc',
                          color: activeAgentIdx === i ? '#fff' : activeAgentIdx > i ? AGENT_COLORS[a] : '#64748b',
                          border: '1px solid #e8edf3',
                        }} />
                        {i < PIPELINE.length - 1 && <ArrowForwardIcon sx={{ fontSize: 9, mx: 0.25, color: '#e2e8f0' }} />}
                      </Box>
                    ))}
                  </Box>
                  <Divider sx={{ mb: 2 }} />
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>Communication Log</Typography>
                  <Box sx={{
                    p: 2, bgcolor: '#f8fafc', border: '1px solid #e8edf3',
                    borderRadius: 2, maxHeight: 320, overflow: 'auto',
                    fontFamily: 'monospace',
                  }}>
                    {(agentLogs.length > 0 ? agentLogs : (selectedIssue.agentLogs || [])).map((log, i) => (
                      <Typography key={i} variant="caption" display="block" sx={{ mb: 0.5, fontSize: '0.72rem', color: '#64748b' }}>
                        <span style={{ color: '#2563eb' }}>[{new Date(log.timestamp).toLocaleTimeString()}]</span>{' '}
                        <span style={{ color: '#7c3aed', fontWeight: 600 }}>{log.agent}:</span>{' '}
                        {log.message}
                      </Typography>
                    ))}
                    {agentLogs.length === 0 && !selectedIssue.agentLogs?.length && (
                      <Typography variant="caption" color="text.secondary">
                        Click Auto Remediate to trigger the agent pipeline…
                      </Typography>
                    )}
                  </Box>
                </Box>
              )}
            </Box>

            {/* Drawer footer */}
            <Box sx={{ p: 2, borderTop: '1px solid #e8edf3', display: 'flex', gap: 1, bgcolor: '#f8fafc' }}>
              <Button onClick={closeDrawer} sx={{ color: '#64748b' }}>Close</Button>
              <Button
                variant="contained" disableElevation
                startIcon={actionLoading === selectedIssue?.id
                  ? <CircularProgress size={14} sx={{ color: 'inherit' }} />
                  : <AutoFixHighIcon sx={{ fontSize: 16 }} />}
                disabled={actionLoading === selectedIssue?.id}
                onClick={() => handleRemediate(selectedIssue)}
                sx={{ flex: 1, bgcolor: '#2563eb', '&:hover': { bgcolor: '#1d4ed8' } }}
              >
                {actionLoading === selectedIssue?.id ? 'Executing…' : 'Execute Remediation'}
              </Button>
            </Box>
          </Box>
        )}
      </Drawer>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={5000}
        onClose={() => setSnackbar(p => ({ ...p, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity={snackbar.severity} onClose={() => setSnackbar(p => ({ ...p, open: false }))} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </>
  );
}

export default IssueCommandCenter;
