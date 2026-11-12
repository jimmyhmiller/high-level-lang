import { Component, Suspense, lazy, useEffect, type ReactNode } from 'react';
import { NavLink, Route, Routes, Navigate, useLocation } from 'react-router-dom';
import { AppBar, Box, Button, Chip, Container, Stack, Toolbar, Typography } from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import PeopleIcon from '@mui/icons-material/People';
import EditNoteIcon from '@mui/icons-material/EditNote';
import AssignmentIcon from '@mui/icons-material/Assignment';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import HubIcon from '@mui/icons-material/Hub';
import ViewInArIcon from '@mui/icons-material/ViewInAr';
import SummarizeIcon from '@mui/icons-material/Summarize';
import AnimationIcon from '@mui/icons-material/Animation';
import * as Sentry from '@sentry/browser';
import { useTranslation } from 'react-i18next';
import { useAppDispatch, useAppSelector, visited } from './store';

const Dashboard = lazy(() => import('./routes/Dashboard'));
const Customers = lazy(() => import('./routes/Customers'));
const Editor = lazy(() => import('./routes/Editor'));
const Forms = lazy(() => import('./routes/Forms'));
const Workflow = lazy(() => import('./routes/Workflow'));
const Graph = lazy(() => import('./routes/Graph'));
const Viewer = lazy(() => import('./routes/Viewer'));
const Reports = lazy(() => import('./routes/Reports'));
const Motion = lazy(() => import('./routes/Motion'));

const NAV = [
  { path: '/dashboard', key: 'dashboard', icon: <DashboardIcon fontSize="small" /> },
  { path: '/customers', key: 'customers', icon: <PeopleIcon fontSize="small" /> },
  { path: '/editor', key: 'editor', icon: <EditNoteIcon fontSize="small" /> },
  { path: '/forms', key: 'forms', icon: <AssignmentIcon fontSize="small" /> },
  { path: '/workflow', key: 'workflow', icon: <AccountTreeIcon fontSize="small" /> },
  { path: '/graph', key: 'graph', icon: <HubIcon fontSize="small" /> },
  { path: '/viewer', key: 'viewer', icon: <ViewInArIcon fontSize="small" /> },
  { path: '/reports', key: 'reports', icon: <SummarizeIcon fontSize="small" /> },
  { path: '/motion', key: 'motion', icon: <AnimationIcon fontSize="small" /> },
];

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error) {
    Sentry.captureException(error);
  }
  render() {
    if (this.state.error) {
      // Rethrown after the frame, so a check of the page sees it as an error, not as a quiet message.
      setTimeout(() => {
        throw this.state.error;
      });
      return <Typography color="error">Something went wrong: {this.state.error.message}</Typography>;
    }
    return this.props.children;
  }
}

function VisitTracker() {
  const location = useLocation();
  const dispatch = useAppDispatch();
  useEffect(() => {
    Sentry.addBreadcrumb({ category: 'navigation', message: location.pathname });
    dispatch(visited(location.pathname));
  }, [location.pathname, dispatch]);
  return null;
}

export default function App() {
  const { t } = useTranslation();
  const visits = useAppSelector((state) => state.ui.visits.length);
  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static" elevation={0}>
        <Toolbar sx={{ gap: 2 }}>
          <Typography variant="h6" component="h1" sx={{ flexGrow: 1 }}>
            {t('app.title')}
          </Typography>
          <Chip size="small" color="secondary" label={`${visits} views`} />
        </Toolbar>
      </AppBar>
      <Stack direction="row" spacing={1} sx={{ px: 2, py: 1, flexWrap: 'wrap' }} component="nav">
        {NAV.map((item) => (
          <Button key={item.path} component={NavLink} to={item.path} startIcon={item.icon} size="small">
            {t(`nav.${item.key}`)}
          </Button>
        ))}
      </Stack>
      <Container maxWidth="lg" sx={{ py: 2 }}>
        <ErrorBoundary>
          <VisitTracker />
          <Suspense fallback={<Typography>{t('app.loading')}</Typography>}>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/customers" element={<Customers />} />
              <Route path="/editor" element={<Editor />} />
              <Route path="/forms" element={<Forms />} />
              <Route path="/workflow" element={<Workflow />} />
              <Route path="/graph" element={<Graph />} />
              <Route path="/viewer" element={<Viewer />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/motion" element={<Motion />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </Container>
    </Box>
  );
}
