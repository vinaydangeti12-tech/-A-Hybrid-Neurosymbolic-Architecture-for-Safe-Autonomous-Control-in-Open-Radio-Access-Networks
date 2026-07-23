import { useState } from 'react';
import { Paper, Typography, Box, Chip, ToggleButton, ToggleButtonGroup, Divider } from '@mui/material';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { format } from 'date-fns';
import ShowChartIcon   from '@mui/icons-material/ShowChart';
import StorageIcon     from '@mui/icons-material/Storage';
import NightlightIcon  from '@mui/icons-material/Nightlight';
import CelebrationIcon from '@mui/icons-material/Celebration';
import HealingIcon     from '@mui/icons-material/Healing';
import RadioButtonCheckedIcon from '@mui/icons-material/RadioButtonChecked';

// ─── Scenario display config ─────────────────────────────────────────────────
const SCENARIO_META = {
  baseline: {
    label: 'Baseline',
    color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe',
    icon: RadioButtonCheckedIcon,
    dataset: 'Zenodo s1',
    datasetDesc: 'Synthetic — steady-state',
  },
  night_mode: {
    label: 'Night Mode (A)',
    color: '#059669', bg: '#f0fdf4', border: '#bbf7d0',
    icon: NightlightIcon,
    dataset: 'Zenodo r1',
    datasetDesc: 'Real — 02:00–05:00 low-traffic',
  },
  festival_mode: {
    label: 'Festival Mode (B)',
    color: '#d97706', bg: '#fffbeb', border: '#fde68a',
    icon: CelebrationIcon,
    dataset: 'Zenodo s1 ×5',
    datasetDesc: 'Synthetic — 500% surge applied',
  },
  self_healing: {
    label: 'Self-Healing (C)',
    color: '#dc2626', bg: '#fef2f2', border: '#fecaca',
    icon: HealingIcon,
    dataset: 'Zenodo r1',
    datasetDesc: 'Real — documented anomaly windows',
  },
};

// ─── Metric lines config ─────────────────────────────────────────────────────
const METRICS = {
  energy:     { key: 'energy',        label: 'Energy %',     color: '#059669', unit: '%' },
  congestion: { key: 'congestion',    label: 'Congestion %', color: '#d97706', unit: '%' },
  anomaly:    { key: 'anomaly_score', label: 'Anomaly Score',color: '#dc2626', unit: '' },
  kpi:        { key: 'kpi_value',     label: 'KPI Value',    color: '#7c3aed', unit: '' },
};

// ─── Stat box ─────────────────────────────────────────────────────────────────
function StatBox({ label, value, unit, color, highlight = false }) {
  return (
    <Box sx={{
      textAlign: 'center',
      p: highlight ? '12px 14px' : '10px 14px',
      borderRadius: 2,
      bgcolor: highlight ? `${color}10` : '#f8fafc',
      border: `1px solid ${highlight ? `${color}30` : '#e8edf3'}`,
      borderTop: `3px solid ${color}`,
      transition: 'background 0.3s, border-color 0.3s',
    }}>
      <Typography sx={{ fontSize: '0.68rem', color: '#94a3b8', display: 'block', mb: 0.5, fontWeight: 500 }}>
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 800, color, lineHeight: 1, fontSize: highlight ? '1.2rem' : '1.05rem' }}>
        {typeof value === 'number' ? value.toFixed(1) : '—'}
        {unit && <Typography component="span" sx={{ fontSize: '0.65rem', color: '#94a3b8', ml: 0.25 }}>{unit}</Typography>}
      </Typography>
    </Box>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <Paper elevation={0} sx={{ p: 1.5, minWidth: 155, boxShadow: '0 4px 16px rgba(15,23,42,0.12)' }}>
      <Typography sx={{ fontSize: '0.72rem', color: '#94a3b8', mb: 0.75, fontWeight: 600 }}>{label}</Typography>
      {payload.map((e, i) => (
        <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
          <Typography sx={{ fontSize: '0.75rem', color: e.color }}>{e.name}</Typography>
          <Typography sx={{ fontSize: '0.75rem', fontWeight: 700 }}>{e.value?.toFixed(2)}</Typography>
        </Box>
      ))}
    </Paper>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────
function StreamingTelemetry({ data, region }) {
  const [view, setView] = useState('all');

  const formatted = data.map(d => ({
    ...d,
    time: format(new Date(d.timestamp || Date.now()), 'HH:mm:ss'),
  }));

  const latest   = data[data.length - 1] || {};
  const scenario = latest.scenario || 'baseline';
  const sm       = SCENARIO_META[scenario] || SCENARIO_META.baseline;
  const ScIcon   = sm.icon;

  const visibleMetrics = view === 'all'
    ? Object.values(METRICS)
    : [METRICS[view]].filter(Boolean);

  // 3σ anomaly threshold (from thesis RQ3)
  const anomalyThreshold = 14;

  return (
    <Box sx={{ p: 3 }}>
      {/* ── Header ── */}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2.5, gap: 2, flexWrap: 'wrap' }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75 }}>
            <ShowChartIcon sx={{ color: 'primary.main', fontSize: 20 }} />
            <Typography variant="h6">Streaming Telemetry</Typography>
          </Box>

          {/* Scenario + Dataset source badges */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Chip
              icon={<ScIcon sx={{ fontSize: '14px !important' }} />}
              label={sm.label}
              size="small"
              sx={{
                bgcolor: sm.bg, color: sm.color,
                border: `1px solid ${sm.border}`,
                fontSize: '0.72rem', height: 22, fontWeight: 600,
              }}
            />
            <Chip
              icon={<StorageIcon sx={{ fontSize: '12px !important' }} />}
              label={sm.dataset}
              size="small"
              sx={{
                bgcolor: '#f8fafc', color: '#475569',
                border: '1px solid #e2e8f0',
                fontSize: '0.68rem', height: 22, fontWeight: 500,
              }}
            />
            <Typography sx={{ fontSize: '0.67rem', color: '#94a3b8' }}>
              {sm.datasetDesc} · {region}
            </Typography>
          </Box>
        </Box>

        {/* Metric filter toggles */}
        <ToggleButtonGroup
          value={view} exclusive
          onChange={(_, v) => v && setView(v)}
          size="small"
          sx={{ '& .MuiToggleButton-root': { px: 1.5, py: 0.5, fontSize: '0.72rem' } }}
        >
          <ToggleButton value="all">All</ToggleButton>
          <ToggleButton value="energy">Energy</ToggleButton>
          <ToggleButton value="congestion">Traffic</ToggleButton>
          <ToggleButton value="anomaly">Anomaly</ToggleButton>
          <ToggleButton value="kpi">KPI</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* ── Chart ── */}
      <Box sx={{ height: 240, mb: 2.5 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={formatted}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={{ stroke: '#e8edf3' }} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} width={32} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: '0.72rem', paddingTop: 10 }} iconType="circle" />
            {(view === 'all' || view === 'anomaly') && (
              <ReferenceLine
                y={anomalyThreshold}
                stroke="#dc2626" strokeDasharray="4 4" strokeOpacity={0.6}
                label={{ value: '3σ threshold', fontSize: 9, fill: '#dc2626', position: 'insideTopRight' }}
              />
            )}
            {visibleMetrics.map(m => (
              <Line
                key={m.key} type="monotone" dataKey={m.key}
                stroke={m.color} strokeWidth={2} dot={false} name={m.label}
                activeDot={{ r: 4, fill: m.color, stroke: '#fff', strokeWidth: 2 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* ── Base stats (always shown) ── */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1.25 }}>
        <StatBox label="Energy %"      value={latest.energy}        unit="%" color="#059669" />
        <StatBox label="Congestion %"  value={latest.congestion}    unit="%" color="#d97706" />
        <StatBox label="Anomaly Score" value={latest.anomaly_score} unit=""  color="#dc2626" />
        <StatBox label="KPI Value"     value={latest.kpi_value}     unit=""  color="#7c3aed" />
      </Box>

      {/* ── Scenario-specific KPI stats (linked directly to thesis metrics) ── */}
      {scenario === 'night_mode' && latest.energy_savings_pct !== undefined && (
        <Box sx={{ mt: 1.25 }}>
          <Typography sx={{ fontSize: '0.67rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.6px', mb: 1 }}>
            RQ1 — Energy Optimisation Metrics
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.25 }}>
            <StatBox label="Energy Saved" value={latest.energy_savings_pct} unit="%" color="#059669" highlight />
            <StatBox label="TRX Active"   value={latest.trx_active}         unit=""  color="#2563eb" highlight />
            <StatBox label="kWh Saved"    value={latest.kwh_saved != null ? latest.kwh_saved * 1000 : null} unit="Wh" color="#059669" highlight />
          </Box>
        </Box>
      )}

      {scenario === 'festival_mode' && latest.call_blocking_probability_pct !== undefined && (
        <Box sx={{ mt: 1.25 }}>
          <Typography sx={{ fontSize: '0.67rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.6px', mb: 1 }}>
            RQ2 — Congestion Control Metrics
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.25 }}>
            <StatBox label="Call Block Prob." value={latest.call_blocking_probability_pct} unit="%" color="#dc2626" highlight />
            <StatBox label="Avg Delay"        value={latest.avg_delay_ms}                  unit="ms" color="#d97706" highlight />
            <StatBox label="Surge Active"     value={latest.surge_active ? 100 : 0}        unit="%" color="#d97706" highlight />
          </Box>
        </Box>
      )}

      {scenario === 'self_healing' && latest.mttd_seconds !== undefined && (
        <Box sx={{ mt: 1.25 }}>
          <Typography sx={{ fontSize: '0.67rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.6px', mb: 1 }}>
            RQ3 — Self-Healing Resilience Metrics
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.25 }}>
            <StatBox label="MTTD"         value={latest.mttd_seconds}          unit="s" color="#dc2626" highlight />
            <StatBox label="MTTR"         value={latest.mttr_seconds}          unit="s" color="#d97706" highlight />
            <StatBox label="Fault Active" value={latest.fault_active ? 1 : 0}  unit=""  color="#dc2626" highlight />
          </Box>
        </Box>
      )}
    </Box>
  );
}

export default StreamingTelemetry;
