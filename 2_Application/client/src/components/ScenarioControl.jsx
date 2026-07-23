import { useState, useEffect } from 'react';
import {
  Box, Paper, Typography, Button, Chip, Grid, Divider,
  CircularProgress, Tooltip, Alert,
} from '@mui/material';
import NightlightIcon from '@mui/icons-material/Nightlight';
import CelebrationIcon from '@mui/icons-material/Celebration';
import HealingIcon from '@mui/icons-material/Healing';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import BugReportIcon from '@mui/icons-material/BugReport';
import RadioButtonCheckedIcon from '@mui/icons-material/RadioButtonChecked';
import { dashboardAPI } from '../services/api';

const SCENARIOS = [
  {
    id: 'baseline',
    label: 'Baseline',
    rq: 'Normal Ops',
    subtitle: 'Standard Operations',
    icon: RadioButtonCheckedIcon,
    color: '#2563eb',
    bgColor: '#eff6ff',
    borderColor: '#bfdbfe',
    description: 'Steady-state monitoring. Agents observe and maintain normal network KPIs.',
    metrics: [],
  },
  {
    id: 'night_mode',
    label: 'Scenario A',
    rq: 'RQ1',
    subtitle: 'Night Mode — Energy Saving',
    icon: NightlightIcon,
    color: '#059669',
    bgColor: '#f0fdf4',
    borderColor: '#6ee7b7',
    description: '02:00–05:00 low-traffic window. The LSTM predicts low load, the Smart Manager picks intent=save_energy, and the Safety Gate clears TRX sleep only where coverage holds.',
    metrics: ['energy_savings_pct', 'trx_shutdown', 'kwh_saved'],
    metricLabels: { energy_savings_pct: 'Energy Saved', trx_shutdown: 'TRX Off', kwh_saved: 'kWh Saved' },
    metricUnits:  { energy_savings_pct: '%', trx_shutdown: '', kwh_saved: 'kWh' },
    thesis: 'KPI: % kWh saved via partial TRX shutdown',
  },
  {
    id: 'festival_mode',
    label: 'Scenario B',
    rq: 'RQ2',
    subtitle: 'Festival Mode — Congestion',
    icon: CelebrationIcon,
    color: '#d97706',
    bgColor: '#fffbeb',
    borderColor: '#fcd34d',
    description: '500% traffic surge injected. The Isolation Forest flags congestion and the LSTM pre-empts the peak; the Local Teams offload load (Safety-Gate checked) to prevent call blocking.',
    metrics: ['call_blocking_probability_pct', 'avg_delay_ms', 'surge_active'],
    metricLabels: { call_blocking_probability_pct: 'Call Block Prob.', avg_delay_ms: 'Avg Delay', surge_active: 'Surge Active' },
    metricUnits:  { call_blocking_probability_pct: '%', avg_delay_ms: 'ms', surge_active: '' },
    thesis: 'KPIs: CBP (Call Blocking Probability), avg delay ms',
  },
  {
    id: 'self_healing',
    label: 'Scenario C',
    rq: 'RQ3',
    subtitle: 'Self-Healing — Fault Recovery',
    icon: HealingIcon,
    color: '#dc2626',
    bgColor: '#fef2f2',
    borderColor: '#fca5a5',
    description: 'Real anomaly-window faults injected. Measures how fast the Isolation Forest SPOTs the fault and the Smart Manager drives an autonomous, Safety-Gate-approved repair.',
    metrics: ['mttd_seconds', 'mttr_seconds', 'faults_injected'],
    metricLabels: { mttd_seconds: 'MTTD', mttr_seconds: 'MTTR', faults_injected: 'Faults' },
    metricUnits:  { mttd_seconds: 's', mttr_seconds: 's', faults_injected: '' },
    thesis: 'KPIs: MTTD (Mean Time to Detect), MTTR (Mean Time to Repair)',
  },
];

function MetricBadge({ label, value, unit, color }) {
  const display = typeof value === 'boolean'
    ? (value ? 'YES' : 'NO')
    : typeof value === 'number'
    ? value.toFixed(value < 10 ? 2 : 0)
    : value ?? '—';

  return (
    <Box sx={{
      px: 1.5, py: 1, borderRadius: 1.5, textAlign: 'center', minWidth: 76,
      bgcolor: '#ffffff', border: `1px solid ${color}30`,
      boxShadow: `inset 0 1px 3px ${color}08`,
    }}>
      <Typography sx={{ fontSize: '0.68rem', color: '#94a3b8', display: 'block', fontWeight: 500 }}>{label}</Typography>
      <Typography sx={{ fontWeight: 700, color, mt: 0.25, fontSize: '0.875rem' }}>
        {display}
        {unit && <Typography component="span" sx={{ fontSize: '0.68rem', color: '#94a3b8', ml: 0.25 }}>{unit}</Typography>}
      </Typography>
    </Box>
  );
}

function fmtTime(s) {
  const m = Math.floor(s / 60), sec = s % 60;
  return `${m}:${String(sec).padStart(2, '0')}`;
}

function ScenarioControl({ onScenarioChange }) {
  const [active, setActive] = useState('baseline');
  const [loading, setLoading] = useState(false);
  const [metrics, setMetrics] = useState({});
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const { data } = await dashboardAPI.getScenarioStatus();
        setActive(data.active_scenario);
        setMetrics(data.metrics || {});
        setElapsed(data.running_seconds || 0);
      } catch (_) {}
    }, 3000);
    return () => clearInterval(poll);
  }, []);

  const activate = async (id) => {
    setLoading(true);
    setError('');
    try {
      await dashboardAPI.activateScenario(id);
      setActive(id);
      setMetrics({});
      setElapsed(0);
      onScenarioChange?.(id);
    } catch (e) {
      setError(`Failed to activate: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const injectFault = async () => {
    try { await dashboardAPI.injectFault('cell_outage'); } catch (_) {}
  };

  const activeScenario = SCENARIOS.find(s => s.id === active) || SCENARIOS[0];

  return (
    <Paper elevation={0} sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 3 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.25 }}>
            Thesis Evaluation Scenarios
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Select a scenario to stream real KPI data from the Zenodo operator dataset
          </Typography>
        </Box>
        {active !== 'baseline' && (
          <Chip
            label={`Running · ${fmtTime(elapsed)}`}
            size="small"
            sx={{
              bgcolor: activeScenario.bgColor,
              color: activeScenario.color,
              border: `1px solid ${activeScenario.borderColor}`,
              fontFamily: 'monospace',
              fontWeight: 700,
              fontSize: '0.75rem',
            }}
          />
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>
      )}

      <Grid container spacing={2}>
        {SCENARIOS.map(sc => {
          const Icon = sc.icon;
          const isActive = active === sc.id;
          return (
            <Grid item xs={12} sm={6} lg={3} key={sc.id}>
              <Paper
                elevation={0}
                sx={{
                  p: 2.25,
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  /* Left accent stripe */
                  borderRadius: '0 10px 10px 0',
                  bgcolor: isActive ? sc.bgColor : '#ffffff',
                  border: `1px solid ${isActive ? sc.borderColor : '#e8edf3'}`,
                  borderLeft: `4px solid ${isActive ? sc.color : `${sc.color}50`}`,
                  transition: 'border-color 0.2s, background-color 0.2s, box-shadow 0.2s',
                  cursor: 'pointer',
                  boxShadow: isActive
                    ? `0 4px 16px ${sc.color}18`
                    : '0 1px 3px rgba(15,23,42,0.05)',
                  '&:hover': {
                    borderColor: sc.borderColor,
                    borderLeft: `4px solid ${sc.color}`,
                    bgcolor: sc.bgColor,
                    boxShadow: `0 4px 16px ${sc.color}18`,
                  },
                }}
                onClick={() => !loading && !isActive && activate(sc.id)}
              >
                {/* Card header */}
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.25, mb: 1.75 }}>
                  <Box sx={{
                    width: 36, height: 36, borderRadius: 2,
                    bgcolor: isActive ? `${sc.color}18` : `${sc.color}0f`,
                    border: `1px solid ${sc.color}30`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                  }}>
                    <Icon sx={{ fontSize: 18, color: sc.color }} />
                  </Box>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.2 }}>
                      <Typography sx={{ color: sc.color, fontWeight: 700, fontSize: '0.67rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                        {sc.label}
                      </Typography>
                      {sc.rq !== 'Normal Ops' && (
                        <Typography sx={{ color: '#94a3b8', fontSize: '0.65rem', fontWeight: 500 }}>
                          · {sc.rq}
                        </Typography>
                      )}
                    </Box>
                    <Typography sx={{ fontWeight: 600, lineHeight: 1.3, fontSize: '0.875rem', color: '#0f172a' }}>
                      {sc.subtitle}
                    </Typography>
                  </Box>
                  {isActive && (
                    <Chip
                      label="ACTIVE"
                      size="small"
                      sx={{
                        bgcolor: sc.color, color: '#fff',
                        fontWeight: 700, fontSize: '0.62rem',
                        height: 20, flexShrink: 0,
                      }}
                    />
                  )}
                </Box>

                {/* Description */}
                <Typography variant="caption" color="text.secondary" sx={{ mb: 1.5, lineHeight: 1.65, display: 'block', flex: 1 }}>
                  {sc.description}
                </Typography>

                {sc.thesis && (
                  <Typography sx={{ color: sc.color, display: 'block', mb: 1.5, fontSize: '0.71rem', fontStyle: 'italic', opacity: 0.85 }}>
                    {sc.thesis}
                  </Typography>
                )}

                {/* Live metrics (active only) */}
                {isActive && Object.keys(metrics).length > 0 && sc.metrics.length > 0 && (
                  <>
                    <Divider sx={{ mb: 1.5 }} />
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 1.5 }}>
                      {sc.metrics.map(key => (
                        <MetricBadge
                          key={key}
                          label={sc.metricLabels?.[key] || key}
                          value={metrics[key]}
                          unit={sc.metricUnits?.[key] || ''}
                          color={sc.color}
                        />
                      ))}
                    </Box>
                  </>
                )}

                {/* Action buttons */}
                <Box sx={{ mt: 'auto', pt: 1.25 }} onClick={e => e.stopPropagation()}>
                  {isActive ? (
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Button
                        size="small" variant="outlined"
                        startIcon={<StopIcon sx={{ fontSize: 15 }} />}
                        onClick={() => activate('baseline')}
                        sx={{
                          flex: 1,
                          borderColor: `${sc.color}60`,
                          color: sc.color,
                          bgcolor: '#ffffff',
                          '&:hover': { bgcolor: sc.bgColor, borderColor: sc.color },
                        }}
                      >
                        Stop
                      </Button>
                      {sc.id === 'self_healing' && (
                        <Tooltip title="Inject a cell fault">
                          <Button
                            size="small" variant="outlined"
                            startIcon={<BugReportIcon sx={{ fontSize: 15 }} />}
                            onClick={injectFault}
                            sx={{ borderColor: '#fca5a5', color: '#dc2626', bgcolor: '#ffffff', '&:hover': { bgcolor: '#fef2f2', borderColor: '#dc2626' } }}
                          >
                            Inject
                          </Button>
                        </Tooltip>
                      )}
                    </Box>
                  ) : (
                    <Button
                      size="small" fullWidth variant="contained" disableElevation
                      startIcon={loading ? <CircularProgress size={13} sx={{ color: 'inherit' }} /> : <PlayArrowIcon sx={{ fontSize: 15 }} />}
                      disabled={loading}
                      onClick={() => activate(sc.id)}
                      sx={{
                        bgcolor: sc.color,
                        boxShadow: `0 2px 8px ${sc.color}35`,
                        '&:hover': { bgcolor: sc.color, filter: 'brightness(0.92)', boxShadow: `0 4px 14px ${sc.color}40` },
                      }}
                    >
                      {loading ? 'Activating…' : 'Activate'}
                    </Button>
                  )}
                </Box>
              </Paper>
            </Grid>
          );
        })}
      </Grid>
    </Paper>
  );
}

export default ScenarioControl;
