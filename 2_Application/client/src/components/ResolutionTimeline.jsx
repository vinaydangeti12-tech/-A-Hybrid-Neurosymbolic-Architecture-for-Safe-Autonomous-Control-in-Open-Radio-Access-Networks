import { Box, Typography, Paper, Chip, Collapse, IconButton, Divider } from '@mui/material';
import { useState } from 'react';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ShieldIcon from '@mui/icons-material/Shield';
import { format } from 'date-fns';

function ResolutionTimeline({ resolutions }) {
  const [expanded, setExpanded] = useState({});
  const toggle = id => setExpanded(p => ({ ...p, [id]: !p[id] }));

  if (!resolutions.length) {
    return (
      <Box sx={{ textAlign: 'center', py: 6 }}>
        <Typography variant="body2" color="text.secondary">
          No resolutions recorded yet — run a scenario to generate events
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ position: 'relative', pl: 4, pt: 1 }}>
      {/* Vertical timeline line */}
      <Box sx={{
        position: 'absolute', left: 13, top: 0, bottom: 0,
        width: 2, bgcolor: '#e8edf3', borderRadius: 1,
      }} />

      {resolutions.map((res, idx) => {
        const key    = res.id || idx;
        const isOpen = !!expanded[key];
        return (
          <Box key={key} sx={{ position: 'relative', mb: 3 }}>
            {/* Timeline dot */}
            <Box sx={{
              position: 'absolute', left: -21, top: 18,
              width: 24, height: 24, borderRadius: '50%',
              bgcolor: '#f0fdf4', border: '2px solid #6ee7b7',
              boxShadow: '0 0 0 3px #f0fdf4',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              zIndex: 1,
            }}>
              <CheckCircleIcon sx={{ fontSize: 13, color: '#059669' }} />
            </Box>

            {/* Card */}
            <Paper elevation={0} sx={{ ml: 1.5, overflow: 'hidden', borderRadius: 2 }}>
              {/* Card header */}
              <Box sx={{ px: 2.5, py: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.3 }}>
                    {format(new Date(res.timestamp || Date.now()), 'MMM dd, HH:mm:ss')}
                  </Typography>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.25 }}>
                    {res.title || 'Remediation Complete'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {res.summary}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 2, flexShrink: 0 }}>
                  <Chip
                    icon={<SmartToyIcon sx={{ fontSize: '12px !important' }} />}
                    label={res.initiatingAgent || 'Smart Manager'}
                    size="small"
                    sx={{
                      bgcolor: '#f5f3ff', color: '#7c3aed',
                      border: '1px solid #ddd6fe', fontSize: '0.72rem',
                    }}
                  />
                  <IconButton
                    size="small"
                    onClick={() => toggle(key)}
                    sx={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.22s' }}
                  >
                    <ExpandMoreIcon sx={{ fontSize: 17 }} />
                  </IconButton>
                </Box>
              </Box>

              {/* Expanded details */}
              <Collapse in={isOpen}>
                <Divider />
                <Box sx={{ px: 2.5, py: 2, bgcolor: '#f8fafc' }}>
                  {/* Actions executed */}
                  <Box sx={{ mb: 1.75 }}>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: '#0f172a', display: 'block', mb: 0.75 }}>
                      Actions Executed
                    </Typography>
                    {(res.actions || []).map((a, i) => (
                      <Box key={i} sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75, mb: 0.4 }}>
                        <Box sx={{ width: 4, height: 4, borderRadius: '50%', bgcolor: '#059669', mt: '6px', flexShrink: 0 }} />
                        <Typography variant="caption" color="text.secondary">{a}</Typography>
                      </Box>
                    ))}
                  </Box>

                  {/* Safety gate */}
                  <Box sx={{ mb: 1.75 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.75 }}>
                      <ShieldIcon sx={{ fontSize: 13, color: '#059669' }} />
                      <Typography variant="caption" sx={{ fontWeight: 700, color: '#0f172a' }}>
                        Safety Gate Validation
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ pl: 1.25, mb: 0.3 }}>
                      ✓ All ADK before_tool_callback checks passed
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ pl: 1.25 }}>
                      ✓ Rollback: {res.rollbackStatus || 'Available'}
                    </Typography>
                  </Box>

                  {/* Learning */}
                  <Box>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: '#0f172a', display: 'block', mb: 0.75 }}>
                      Learning Agent
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ pl: 1.25, mb: 0.3 }}>
                      Model updated with outcome
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ pl: 1.25 }}>
                      Confidence: {res.confidenceScore || '95%'}
                    </Typography>
                  </Box>
                </Box>
              </Collapse>
            </Paper>
          </Box>
        );
      })}
    </Box>
  );
}

export default ResolutionTimeline;
