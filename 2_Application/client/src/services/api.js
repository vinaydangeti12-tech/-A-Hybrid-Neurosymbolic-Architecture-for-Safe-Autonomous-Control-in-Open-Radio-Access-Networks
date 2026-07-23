import axios from 'axios';

// Empty default → same-origin relative URLs, so the Vite dev proxy (/api) is
// used in dev and the app still works when served behind any host in prod.
// Override with VITE_API_URL to point at a different backend.
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.response.use(
  r => r,
  e => { console.error('API Error:', e); return Promise.reject(e); }
);

export const dashboardAPI = {
  getTelemetry:        (region) => api.get('/api/telemetry', { params: { region } }),
  getActiveUsers:      (region) => api.get(`/api/active-users/${region}`),
  getIssues:           (region) => api.get('/api/issues', { params: { region } }),
  getSystemHealth:     (region) => api.get(`/api/health/${region}`),
  getResolutions:      (region, limit = 20) => api.get('/api/resolutions', { params: { region, limit } }),
  getAgentStatus:      () => api.get('/api/agents/status'),
  getIntegrationStatus:() => api.get('/api/integration/status'),

  triggerRemediation:  (issueId, action, region = 'region-IE-01') =>
    api.post('/api/remediation/trigger', { issueId, action, region }),

  analyzeIssue:        (issueId, issue, region = 'region-IE-01') =>
    api.post('/api/issue/analyze', { issueId, issue, region }),

  chatWithAI:          (message, context = 'trace_dashboard') =>
    api.post('/api/chat', { message, context }),

  // Scenario endpoints (thesis evaluation)
  activateScenario:    (scenario) => api.post('/api/scenario/activate', { scenario }),
  getScenarioStatus:   () => api.get('/api/scenario/status'),
  injectFault:         (fault_type = 'cell_outage') => api.post('/api/scenario/inject_fault', { fault_type }),

  createIssue:         (region, severity, issue_type) =>
    api.post('/api/issues/create', { region, severity, issue_type }),
  setDemoMode:         (enabled, auto_heal = true, interval = 10) =>
    api.post('/api/demo/mode', { enabled, auto_heal, interval }),

  // Dataset endpoints
  getDatasetOverview:  () => api.get('/api/dataset/overview'),
  getDatasetSeries:    (seriesId, points = 500, offset = 0) =>
    api.get(`/api/dataset/series/${seriesId}`, { params: { points, offset } }),
  getDatasetIncidents: () => api.get('/api/dataset/incidents'),
};

export default api;
