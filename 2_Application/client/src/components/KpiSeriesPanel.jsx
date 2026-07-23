import { useState, useEffect, useCallback } from 'react';
import {
  Box, Paper, Typography, Select, MenuItem, FormControl,
  CircularProgress, Chip, Divider, ToggleButton, ToggleButtonGroup,
} from '@mui/material';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import StorageIcon from '@mui/icons-material/Storage';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { dashboardAPI } from '../services/api';

const REAL_IDS  = Array.from({ length: 14 }, (_, i) => `r${i + 1}`);
const SYNTH_IDS = Array.from({ length: 50 }, (_, i) => `s${i + 1}`);

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <Paper elevation={0} sx={{ p: 1.5, minWidth: 120, boxShadow: '0 4px 16px rgba(15,23,42,0.12)' }}>
      <Typography sx={{ fontSize: '0.7rem', color: '#94a3b8', display: 'block', mb: 0.5 }}>Sample #{d.idx}</Typography>
      <Typography sx={{ fontWeight: 700, color: '#2563eb', fontSize: '0.875rem' }}>KPI: {d.v?.toFixed(1)}</Typography>
    </Paper>
  );
};

function KpiSeriesPanel() {
  const [seriesType, setSeriesType]         = useState('real');
  const [seriesId, setSeriesId]             = useState('r1');
  const [data, setData]                     = useState([]);
  const [anomalyWindows, setAnomalyWindows] = useState([]);
  const [loading, setLoading]               = useState(false);
  const [overview, setOverview]             = useState(null);

  useEffect(() => {
    dashboardAPI.getDatasetOverview().then(r => setOverview(r.data)).catch(() => {});
  }, []);

  const loadSeries = useCallback(async (id) => {
    setLoading(true);
    try {
      const { data: resp } = await dashboardAPI.getDatasetSeries(id, 500);
      setData(resp.data || []);
      setAnomalyWindows(resp.anomaly_windows || []);
    } catch (_) {
      setData([]);
      setAnomalyWindows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSeries(seriesId); }, [seriesId, loadSeries]);

  const handleTypeChange = (_, v) => {
    if (!v) return;
    setSeriesType(v);
    setSeriesId(v === 'real' ? 'r1' : 's1');
  };

  const ids        = seriesType === 'real' ? REAL_IDS : SYNTH_IDS;
  const hasAnomalies = anomalyWindows.length > 0;
  const kpiValues  = data.map(d => d.v);
  const mean = kpiValues.length ? kpiValues.reduce((a, b) => a + b, 0) / kpiValues.length : 0;
  const max  = kpiValues.length ? Math.max(...kpiValues) : 0;
  const min  = kpiValues.length ? Math.min(...kpiValues) : 0;

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2.5 }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.4 }}>
            <StorageIcon sx={{ color: 'primary.main', fontSize: 20 }} />
            <Typography variant="h6">Dataset Explorer</Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">
            Zenodo Network Operator KPIs · {overview?.total_samples?.toLocaleString() ?? '665,756'} samples
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {loading && <CircularProgress size={14} sx={{ color: 'primary.main' }} />}
          {hasAnomalies && (
            <Chip
              icon={<WarningAmberIcon sx={{ fontSize: '14px !important' }} />}
              label={`${anomalyWindows.length} anomaly${anomalyWindows.length > 1 ? 's' : ''}`}
              size="small"
              color="warning"
              sx={{ fontWeight: 600 }}
            />
          )}
          <Chip
            label={seriesType === 'real' ? 'Real Data' : 'Synthetic'}
            size="small"
            sx={{
              bgcolor: seriesType === 'real' ? '#eff6ff' : '#f5f3ff',
              color:   seriesType === 'real' ? '#2563eb' : '#7c3aed',
              border: `1px solid ${seriesType === 'real' ? '#bfdbfe' : '#ddd6fe'}`,
              fontWeight: 600,
            }}
          />
        </Box>
      </Box>

      {/* Series selector */}
      <Box sx={{ display: 'flex', gap: 1.5, mb: 2.5, alignItems: 'center', flexWrap: 'wrap' }}>
        <ToggleButtonGroup
          value={seriesType} exclusive onChange={handleTypeChange} size="small"
          sx={{ '& .MuiToggleButton-root': { px: 1.75, py: 0.5, fontSize: '0.72rem' } }}
        >
          <ToggleButton value="real">Real (r1–r14)</ToggleButton>
          <ToggleButton value="synthetic">Synthetic (s1–s48)</ToggleButton>
        </ToggleButtonGroup>

        <FormControl size="small" sx={{ minWidth: 100 }}>
          <Select
            value={seriesId}
            onChange={e => setSeriesId(e.target.value)}
            sx={{
              bgcolor: '#f8fafc',
              '& .MuiOutlinedInput-notchedOutline': { borderColor: '#e2e8f0' },
            }}
          >
            {ids.map(id => (
              <MenuItem key={id} value={id} sx={{ fontSize: '0.875rem' }}>
                {id.toUpperCase()}{seriesType === 'real' && id === 'r12' ? ' ★ major fault' : ''}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {/* Chart */}
      <Box sx={{ height: 210, mb: 2.5 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="kpiGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#2563eb" stopOpacity={0.18} />
                <stop offset="100%" stopColor="#2563eb" stopOpacity={0.01} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis
              dataKey="idx"
              tick={{ fontSize: 10, fill: '#94a3b8' }}
              axisLine={{ stroke: '#e8edf3' }}
              tickLine={false}
              tickFormatter={v => `#${v}`}
              interval={Math.floor(data.length / 6)}
            />
            <YAxis
              domain={[0, 1000]}
              tick={{ fontSize: 10, fill: '#94a3b8' }}
              axisLine={false}
              tickLine={false}
              width={32}
            />
            <Tooltip content={<CustomTooltip />} />
            {anomalyWindows.map((w, i) => {
              // The X axis is keyed on `idx` (the real sample number), so the
              // reference line must sit at the matching idx value — not the
              // array position. Using findIndex put every fault marker at the
              // wrong place on the chart.
              const pt = data.find(d => d.idx >= w.start);
              return pt ? (
                <ReferenceLine
                  key={`a-${i}`}
                  x={pt.idx}
                  stroke="#dc2626"
                  strokeDasharray="3 3"
                  strokeOpacity={0.7}
                  label={{ value: 'Fault', fontSize: 9, fill: '#dc2626' }}
                />
              ) : null;
            })}
            <Area
              type="monotone"
              dataKey="v"
              stroke="#2563eb"
              strokeWidth={2}
              fill="url(#kpiGrad)"
              dot={false}
              name="KPI"
              activeDot={{ r: 4, fill: '#2563eb', stroke: '#fff', strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* Stats row */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.25 }}>
        {[
          { label: 'Mean KPI', value: mean.toFixed(1), color: '#2563eb' },
          { label: 'Peak KPI', value: max.toFixed(1),  color: '#d97706' },
          { label: 'Min KPI',  value: min.toFixed(1),  color: '#64748b' },
        ].map(({ label, value, color }) => (
          <Box key={label} sx={{
            textAlign: 'center', p: '10px 14px', borderRadius: 2,
            bgcolor: '#f8fafc', border: '1px solid #e8edf3',
            borderTop: `3px solid ${color}`,
          }}>
            <Typography sx={{ fontSize: '0.68rem', color: '#94a3b8', display: 'block', mb: 0.5, fontWeight: 500 }}>
              {label}
            </Typography>
            <Typography sx={{ fontWeight: 800, color, fontSize: '1.1rem', lineHeight: 1 }}>{value}</Typography>
          </Box>
        ))}
      </Box>

      {/* Anomaly windows list */}
      {hasAnomalies && (
        <Box sx={{
          mt: 1.5, p: 1.5,
          bgcolor: '#fef2f2', border: '1px solid #fecaca',
          borderLeft: '3px solid #dc2626',
          borderRadius: '0 8px 8px 0',
        }}>
          <Typography sx={{ color: '#b91c1c', fontWeight: 700, fontSize: '0.75rem', mb: 0.75 }}>
            {anomalyWindows.length} labelled anomaly window{anomalyWindows.length > 1 ? 's' : ''} — {seriesId.toUpperCase()}
          </Typography>
          {anomalyWindows.map((w, i) => (
            <Typography key={i} sx={{ color: '#64748b', display: 'block', mt: 0.25, fontSize: '0.72rem' }}>
              Sample {w.start}–{w.end} &nbsp;({w.end - w.start} samples, ~{Math.round((w.end - w.start) * 5 / 60)} h)
            </Typography>
          ))}
        </Box>
      )}
    </Box>
  );
}

export default KpiSeriesPanel;
