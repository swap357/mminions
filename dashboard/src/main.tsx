import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './index.css';
import App from './App';
import { RunDetail } from './pages/RunDetail';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 1000 } },
});

function EmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center text-neutral-600 text-sm">
      select a run or launch a new one
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<App />}>
            <Route index element={<EmptyState />} />
            <Route path="runs/:runId" element={<RunDetail />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
