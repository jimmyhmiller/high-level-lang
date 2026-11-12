import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CssBaseline } from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import * as Sentry from '@sentry/browser';
import { store } from './store';
import './i18n';
import App from './App';

// No DSN: the SDK runs its integrations and records breadcrumbs, and sends nothing.
Sentry.init({
  dsn: undefined,
  release: 'field-ops@2.4.1',
  integrations: [Sentry.browserTracingIntegration()],
  tracesSampleRate: 0,
});

const theme = createTheme({
  palette: { primary: { main: '#1b4d89' }, secondary: { main: '#c2185b' } },
  shape: { borderRadius: 6 },
  typography: { fontFamily: 'system-ui, sans-serif' },
});

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: false, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider store={store}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ThemeProvider>
      </QueryClientProvider>
    </Provider>
  </StrictMode>,
);
