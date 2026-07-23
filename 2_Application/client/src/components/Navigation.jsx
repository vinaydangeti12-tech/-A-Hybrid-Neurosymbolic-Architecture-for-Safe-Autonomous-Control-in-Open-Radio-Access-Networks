import { AppBar, Toolbar, Tabs, Tab, Box, Typography, Chip } from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import HubIcon from '@mui/icons-material/Hub';

function Navigation() {
  const navigate = useNavigate();
  const location = useLocation();
  const currentTab = location.pathname === '/chat' ? 1 : 0;

  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{
        bgcolor: '#ffffff',
        borderBottom: '1px solid #e8edf3',
        boxShadow: '0 1px 5px rgba(15,23,42,0.06)',
      }}
    >
      {/* Blue → purple accent stripe */}
      <Box sx={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 3,
        background: 'linear-gradient(90deg, #2563eb 0%, #7c3aed 100%)',
        zIndex: 1,
      }} />

      <Toolbar sx={{ justifyContent: 'space-between', minHeight: 64, pt: '3px' }}>

        {/* Brand */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box sx={{
            width: 38, height: 38, borderRadius: 2,
            background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 10px rgba(37,99,235,0.25)',
            flexShrink: 0,
          }}>
            <HubIcon sx={{ color: 'white', fontSize: 20 }} />
          </Box>
          <Box>
            <Typography sx={{ fontWeight: 800, color: '#0f172a', lineHeight: 1.1, fontSize: '1rem', letterSpacing: '-0.4px' }}>
              H-TRACE
            </Typography>
            <Typography sx={{ color: '#94a3b8', fontSize: '0.67rem', lineHeight: 1, fontWeight: 400 }}>
              Hybrid Tiered Reasoning + Algorithmic Control · O-RAN
            </Typography>
          </Box>
        </Box>

        {/* Navigation tabs */}
        <Tabs
          value={currentTab}
          onChange={(_, v) => navigate(v === 0 ? '/' : '/chat')}
          sx={{
            '& .MuiTabs-indicator': { height: 3, borderRadius: '3px 3px 0 0', bgcolor: '#2563eb' },
            '& .MuiTab-root': {
              color: '#64748b', minHeight: 64, px: 3,
              fontSize: '0.875rem', fontWeight: 500, pt: '3px',
            },
            '& .MuiTab-root.Mui-selected': { color: '#1d4ed8', fontWeight: 600 },
            '& .MuiTab-root:hover': { color: '#334155', bgcolor: 'rgba(15,23,42,0.02)' },
          }}
        >
          <Tab icon={<DashboardIcon sx={{ fontSize: 18 }} />} label="Dashboard" iconPosition="start" />
          <Tab icon={<SmartToyIcon sx={{ fontSize: 18 }} />} label="Smart Manager" iconPosition="start" />
        </Tabs>

        {/* Right: thesis info + status */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip
            icon={<Box className="status-online" sx={{ ml: 1 }} />}
            label="System Online"
            size="small"
            sx={{
              bgcolor: '#f0fdf4',
              border: '1px solid #bbf7d0',
              color: '#047857',
              fontWeight: 600,
              fontSize: '0.75rem',
            }}
          />
        </Box>
      </Toolbar>
    </AppBar>
  );
}

export default Navigation;
