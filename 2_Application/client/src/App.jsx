import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navigation from './components/Navigation';
import Dashboard from './components/Dashboard';
import ChatInterface from './components/ChatInterface';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary:    { main: '#2563eb', light: '#60a5fa', dark: '#1d4ed8', contrastText: '#fff' },
    secondary:  { main: '#7c3aed', light: '#a78bfa', dark: '#5b21b6', contrastText: '#fff' },
    background: { default: '#f8fafc', paper: '#ffffff' },
    success:    { main: '#059669', light: '#34d399', dark: '#047857' },
    warning:    { main: '#d97706', light: '#fbbf24', dark: '#b45309' },
    error:      { main: '#dc2626', light: '#f87171', dark: '#b91c1c' },
    info:       { main: '#0284c7', light: '#38bdf8', dark: '#0369a1' },
    text:       { primary: '#0f172a', secondary: '#64748b', disabled: '#94a3b8' },
    divider:    '#e8edf3',
  },
  typography: {
    fontFamily: '"Inter", "Segoe UI", Roboto, system-ui, sans-serif',
    button:    { textTransform: 'none', fontWeight: 600 },
    h4:        { fontWeight: 700, letterSpacing: '-0.5px' },
    h5:        { fontWeight: 700, letterSpacing: '-0.4px' },
    h6:        { fontWeight: 600, letterSpacing: '-0.2px' },
    subtitle1: { fontWeight: 600 },
    subtitle2: { fontWeight: 600 },
    body2:     { lineHeight: 1.65 },
    caption:   { lineHeight: 1.5 },
  },
  shape: { borderRadius: 10 },
  shadows: [
    'none',
    '0 1px 3px rgba(15,23,42,0.07)',
    '0 4px 8px rgba(15,23,42,0.07)',
    '0 8px 16px rgba(15,23,42,0.08)',
    '0 16px 24px rgba(15,23,42,0.09)',
    '0 24px 40px rgba(15,23,42,0.12)',
    ...Array(19).fill('0 4px 12px rgba(15,23,42,0.07)'),
  ],
  components: {
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          border: '1px solid #e8edf3',
          boxShadow: '0 1px 3px rgba(15,23,42,0.06)',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          border: '1px solid #e8edf3',
          boxShadow: '0 1px 3px rgba(15,23,42,0.06)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root:      { borderRadius: 8, padding: '7px 18px' },
        contained: { boxShadow: '0 1px 2px rgba(0,0,0,0.08)', '&:hover': { boxShadow: '0 4px 14px rgba(0,0,0,0.12)' } },
        outlined:  { borderColor: '#d1d9e6', '&:hover': { borderColor: '#2563eb', bgcolor: '#eff6ff' } },
      },
    },
    MuiChip: {
      styleOverrides: { root: { fontWeight: 500 } },
    },
    MuiTab: {
      styleOverrides: { root: { textTransform: 'none', fontWeight: 500 } },
    },
    MuiAppBar: {
      styleOverrides: { root: { backgroundImage: 'none' } },
    },
    MuiLinearProgress: {
      styleOverrides: { root: { borderRadius: 4 } },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          borderColor: '#e2e8f0',
          color: '#64748b',
          fontSize: '0.75rem',
          '&.Mui-selected': { bgcolor: '#eff6ff', color: '#2563eb', borderColor: '#bfdbfe', '&:hover': { bgcolor: '#dbeafe' } },
          '&:hover': { bgcolor: '#f8fafc' },
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: { border: 'none', boxShadow: '-4px 0 24px rgba(15,23,42,0.10)' },
      },
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Navigation />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/chat" element={<ChatInterface />} />
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;
