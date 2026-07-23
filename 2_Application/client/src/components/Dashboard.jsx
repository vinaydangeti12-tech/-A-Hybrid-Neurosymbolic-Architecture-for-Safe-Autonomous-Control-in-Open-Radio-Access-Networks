import { useState, useEffect, useCallback } from 'react';
import { Box, Container, Grid, Paper, Tab, Tabs, Typography, Divider, Chip } from '@mui/material';
import BugReportIcon      from '@mui/icons-material/BugReport';
import HeroStrip          from './HeroStrip';
import StreamingTelemetry from './StreamingTelemetry';
import KpiSeriesPanel     from './KpiSeriesPanel';
import IssueCommandCenter from './IssueCommandCenter';
import ResolutionTimeline from './ResolutionTimeline';
import ScenarioControl    from './ScenarioControl';
import { WebSocketService } from '../services/websocket';
import { dashboardAPI } from '../services/api';

function Dashboard() {
  const [selectedRegion,  setSelectedRegion]  = useState('region-IE-01');
  const [telemetryData,   setTelemetryData]   = useState([]);
  const [issues,          setIssues]          = useState([]);
  const [resolutions,     setResolutions]     = useState([]);
  const [globalHealth,    setGlobalHealth]    = useState(95);
  const [systemStatus,    setSystemStatus]    = useState('Operational');
  const [lastRemediation, setLastRemediation] = useState('No recent actions');
  const [activeTab,       setActiveTab]       = useState(0);
  const [activeScenario,  setActiveScenario]  = useState('baseline');

  const fetchIssues = useCallback(async (region) => {
    try {
      const res = await dashboardAPI.getIssues(region);
      setIssues((res.data || []).filter(i => i.status !== 'Resolved'));
    } catch (_) {}
  }, []);

  useEffect(() => {
    const ws = WebSocketService.getInstance();
    ws.connect(() => { ws.subscribeToRegion(selectedRegion); fetchIssues(selectedRegion); });

    const onTelemetry       = d => setTelemetryData(p => [...p.slice(-120), d]);
    const onIssue           = d => setIssues(p => {
      if (p.some(i => i.id === d.id) || d.status === 'Resolved') return p;
      return [d, ...p];
    });
    const onResolution      = d => {
      setResolutions(p => [d, ...p]);
      setLastRemediation(d.summary);
      if (d.issueId) setIssues(p => p.filter(i => i.id !== d.issueId));
    };
    const onHealth          = d => { setGlobalHealth(d.score); setSystemStatus(d.status); };
    const onScenarioChanged = d => setActiveScenario(d.active_scenario || 'baseline');

    ws.on('telemetry',        onTelemetry);
    ws.on('issue',            onIssue);
    ws.on('resolution',       onResolution);
    ws.on('health',           onHealth);
    ws.on('scenario_changed', onScenarioChanged);

    return () => {
      ws.off('telemetry',        onTelemetry);
      ws.off('issue',            onIssue);
      ws.off('resolution',       onResolution);
      ws.off('health',           onHealth);
      ws.off('scenario_changed', onScenarioChanged);
      ws.disconnect();
    };
  }, [selectedRegion, fetchIssues]);

  return (
    <Box sx={{ bgcolor: 'background.default', minHeight: 'calc(100vh - 64px)', pb: 6 }}>

      <HeroStrip
        selectedRegion={selectedRegion}
        onRegionChange={r => { setSelectedRegion(r); WebSocketService.getInstance().subscribeToRegion(r); }}
        globalHealth={globalHealth}
        systemStatus={systemStatus}
        lastRemediation={lastRemediation}
      />

      <Container maxWidth="xl" sx={{ mt: 3 }}>
        <Grid container spacing={3}>

          {/* ── Scenario Selector ── */}
          <Grid item xs={12}>
            <ScenarioControl onScenarioChange={setActiveScenario} />
          </Grid>

          {/* ── Streaming Telemetry ── */}
          <Grid item xs={12} lg={7}>
            <Paper elevation={0} sx={{ height: '100%' }}>
              <StreamingTelemetry data={telemetryData} region={selectedRegion} />
            </Paper>
          </Grid>

          {/* ── Dataset Explorer ── */}
          <Grid item xs={12} lg={5}>
            <Paper elevation={0} sx={{ height: '100%' }}>
              <KpiSeriesPanel />
            </Paper>
          </Grid>

          {/* ── Issue Command Centre ── */}
          <Grid item xs={12}>
            <Paper elevation={0} sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
                    <BugReportIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                    <Typography variant="h6">Issue Command Centre</Typography>
                    {issues.length > 0 && (
                      <Chip label={issues.length} size="small" color="error"
                        sx={{ height: 20, fontSize: '0.7rem', fontWeight: 700 }} />
                    )}
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    Faults SPOTted by the ML Local Teams (Isolation Forest) · every remediation cleared by the deterministic Safety Gate
                  </Typography>
                </Box>
                <Tabs
                  value={activeTab}
                  onChange={(_, v) => setActiveTab(v)}
                  sx={{
                    '& .MuiTabs-indicator': { height: 2, bgcolor: 'primary.main' },
                    '& .MuiTab-root': { fontSize: '0.82rem', minHeight: 42 },
                  }}
                >
                  <Tab label="Live Issues" />
                  <Tab label="Resolution Timeline" />
                </Tabs>
              </Box>

              <Divider sx={{ mb: 2.5 }} />

              {activeTab === 0 && (
                <IssueCommandCenter
                  issues={issues}
                  onIssueResolved={id => setIssues(p => p.filter(i => i.id !== id))}
                />
              )}
              {activeTab === 1 && <ResolutionTimeline resolutions={resolutions} />}
            </Paper>
          </Grid>

        </Grid>
      </Container>
    </Box>
  );
}

export default Dashboard;
