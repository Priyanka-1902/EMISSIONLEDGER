import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '../stores/auth'
import { AppShell } from '../components/layout/AppShell'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { Toaster } from '../components/ui/Toaster'
import '../i18n/config'

// Lazy-loaded route chunks for code splitting
const Dashboard = lazy(() => import('../pages/Dashboard'))
const CBAMReports = lazy(() => import('../pages/CBAMReports'))
const CBAMReportDetail = lazy(() => import('../pages/CBAMReportDetail'))
const DataIngestion = lazy(() => import('../pages/DataIngestion'))
const EmissionRecords = lazy(() => import('../pages/EmissionRecords'))
const Facilities = lazy(() => import('../pages/Facilities'))
const Settings = lazy(() => import('../pages/Settings'))
const Onboarding = lazy(() => import('../pages/Onboarding'))
const Login = lazy(() => import('../pages/Login'))
const AuditLog = lazy(() => import('../pages/AuditLog'))
const CarbonCredits = lazy(() => import('../pages/CarbonCredits'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,  // 5 min
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore()
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<LoadingSpinner fullscreen />}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AppShell />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="cbam">
                <Route index element={<CBAMReports />} />
                <Route path=":reportId" element={<CBAMReportDetail />} />
              </Route>
              <Route path="emissions" element={<EmissionRecords />} />
              <Route path="ingestion" element={<DataIngestion />} />
              <Route path="facilities" element={<Facilities />} />
              <Route path="credits" element={<CarbonCredits />} />
              <Route path="audit" element={<AuditLog />} />
              <Route path="settings" element={<Settings />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
