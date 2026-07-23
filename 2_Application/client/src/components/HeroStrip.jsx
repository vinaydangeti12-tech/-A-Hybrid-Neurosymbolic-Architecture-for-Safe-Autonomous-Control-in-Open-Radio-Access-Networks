import { Box, Paper, Typography, FormControl, Select, MenuItem, Chip, Grid } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import ErrorIcon from '@mui/icons-material/Error';
import SignalCellularAltIcon from '@mui/icons-material/SignalCellularAlt';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import SecurityIcon from '@mui/icons-material/Security';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';

const REGIONS = [
  { id: 'region-IE-01', name: 'Dublin (IE-01)' },
  { id: 'region-IE-02', name: 'Cork (IE-02)' },
  { id: 'region-DE-01', name: 'Berlin (DE-01)' },
];

function HealthRing({ score }) {
  const color = score >= 90 ? '#059669' : score >= 70 ? '#d97706' : '#dc2626';
  const bg    = score >= 90 ? '#f0fdf4' : score >= 70 ? '#fffbeb' : '#fef2f2';
  const ring  = score >= 90 ? '#6ee7b7' : score >= 70 ? '#fcd34d' : '#fca5a5';
  return (
    <Box sx={{
      width: 58, height: 58, borderRadius: '50%',
      background: bg,
      border: `3px solid ${ring}`,
      boxShadow: `0 0 0 2px ${color}18`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexShrink: 0,
    }}>
      <Typography sx={{ fontWeight: 800, color, fontSize: '1.1rem', lineHeight: 1 }}>
        {Math.round(score)}
      </Typography>
    </Box>
  );
}

function TileLabel({ icon, label }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.25 }}>
      {icon}
      <Typography sx={{
        fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.7px', fontSize: '0.67rem', color: '#94a3b8',
      }}>
        {label}
      </Typography>
    </Box>
  );
}

function HeroStrip({ selectedRegion, onRegionChange, globalHealth, systemStatus, lastRemediation }) {
  const isOk  = systemStatus === 'Operational' || systemStatus === 'Healthy';
  const isDeg = systemStatus === 'Degraded';
  const StatusIcon  = isOk ? CheckCircleIcon : isDeg ? WarningIcon : ErrorIcon;
  const statusColor = isOk ? 'success' : isDeg ? 'warning' : 'error';

  return (
    <Paper
      elevation={0}
      sx={{ mx: 3, mt: 3, px: 3, py: 2.75, borderRadius: 2 }}
    >
      <Grid container spacing={3} alignItems="flex-start">

        {/* Tile 1 — Region selector */}
        <Grid item xs={12} sm={6} md={3}>
          <TileLabel icon={<SignalCellularAltIcon sx={{ color: '#2563eb', fontSize: 15 }} />} label="Network Region" />
          <FormControl size="small" fullWidth>
            <Select
              value={selectedRegion}
              onChange={e => onRegionChange(e.target.value)}
              sx={{
                bgcolor: '#f8fafc',
                '& .MuiOutlinedInput-notchedOutline': { borderColor: '#e2e8f0' },
                '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: '#94a3b8' },
              }}
            >
              {REGIONS.map(r => (
                <MenuItem key={r.id} value={r.id}>{r.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        {/* Tile 2 — Global health */}
        <Grid item xs={12} sm={6} md={3}>
          <TileLabel icon={<MonitorHeartIcon sx={{ color: '#2563eb', fontSize: 15 }} />} label="Global Health" />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <HealthRing score={globalHealth} />
            <Box>
              <Chip
                label={systemStatus}
                color={statusColor}
                icon={<StatusIcon sx={{ fontSize: '14px !important' }} />}
                size="small"
                sx={{ fontWeight: 600, mb: 0.75, fontSize: '0.75rem' }}
              />
              <Typography sx={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block' }}>
                H-TRACE neurosymbolic control
              </Typography>
            </Box>
          </Box>
        </Grid>

        {/* Tile 3 — Neurosymbolic tiers */}
        <Grid item xs={12} sm={6} md={3}>
          <TileLabel icon={<SecurityIcon sx={{ color: '#059669', fontSize: 15 }} />} label="Neurosymbolic Tiers" />
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.85 }}>
            {[
              { label: 'AI · Smart Manager',      indent: 0 },
              { label: 'ML · Local Teams (A/B)',  indent: 1 },
              { label: 'Safety Gate · rules',     indent: 2 },
            ].map(({ label, indent }) => (
              <Box key={label} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, pl: indent * 1.25 }}>
                <Box className="status-online" />
                <Typography sx={{ fontSize: '0.8rem', color: '#334155', fontWeight: 500 }}>{label}</Typography>
              </Box>
            ))}
          </Box>
        </Grid>

        {/* Tile 4 — Last remediation */}
        <Grid item xs={12} sm={6} md={3}>
          <TileLabel icon={<AutoFixHighIcon sx={{ color: '#d97706', fontSize: 15 }} />} label="Last Auto-Remediation" />
          <Box sx={{
            px: 1.5, py: 1.25,
            bgcolor: '#fafbfc',
            border: '1px solid #e8edf3',
            borderLeft: '3px solid #d97706',
            borderRadius: '0 8px 8px 0',
          }}>
            <Typography sx={{ color: '#475569', lineHeight: 1.6, fontSize: '0.8rem', display: 'block' }}>
              {lastRemediation || 'No recent actions'}
            </Typography>
          </Box>
        </Grid>

      </Grid>

      {/* Design guarantees — the neurosymbolic claims (validated over 474 episodes) */}
      <Box sx={{
        mt: 2.5, pt: 2, borderTop: '1px dashed #e2e8f0',
        display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1.25,
      }}>
        <Typography sx={{
          fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.7px',
          fontSize: '0.62rem', color: '#94a3b8', mr: 0.5,
        }}>
          Design Guarantees
        </Typography>
        {[
          { c: '#7c3aed', label: '0% control-loop hallucination', sub: 'generative AI kept out of the real-time loop' },
          { c: '#dc2626', label: '0% false-pass', sub: 'deterministic Safety Gate · formal guarantee' },
          { c: '#0284c7', label: '< 100 ms decision latency', sub: 'within the Near-RT RIC budget' },
        ].map(({ c, label, sub }) => (
          <Box key={label} title={sub} sx={{
            display: 'flex', alignItems: 'center', gap: 0.75,
            px: 1.25, py: 0.6, borderRadius: 1.5,
            bgcolor: `${c}0d`, border: `1px solid ${c}33`,
          }}>
            <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: c, flexShrink: 0 }} />
            <Typography sx={{ fontSize: '0.74rem', fontWeight: 700, color: c }}>{label}</Typography>
            <Typography sx={{ fontSize: '0.66rem', color: '#94a3b8', display: { xs: 'none', lg: 'block' } }}>
              · {sub}
            </Typography>
          </Box>
        ))}
        <Typography sx={{ fontSize: '0.66rem', color: '#cbd5e1', ml: 'auto', fontStyle: 'italic' }}>
          validated over 474 episodes · Rule of Three (hallucination true rate &lt; 0.64% at 95% CI)
        </Typography>
      </Box>
    </Paper>
  );
}

export default HeroStrip;
