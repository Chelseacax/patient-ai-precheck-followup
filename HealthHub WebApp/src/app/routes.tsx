import { createBrowserRouter, Navigate } from 'react-router';
import type { ReactNode } from 'react';
import { Layout } from './components/Layout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { LabReportsPage } from './pages/LabReportsPage';
import { AppointmentsPage } from './pages/AppointmentsPage';
import { PaymentsPage } from './pages/PaymentsPage';
import { ImmunisationsPage } from './pages/ImmunisationsPage';
import { ProfilePage } from './pages/ProfilePage';

function RequireAuth({ children }: { children: ReactNode }) {
  const isAuthed = localStorage.getItem('hh_auth') === '1';
  if (!isAuthed) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <LoginPage />,
  },
  {
    path: '/app',
    element: (
      <RequireAuth>
        <Layout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'lab-reports', element: <LabReportsPage /> },
      { path: 'appointments', element: <AppointmentsPage /> },
      { path: 'payments', element: <PaymentsPage /> },
      { path: 'immunisations', element: <ImmunisationsPage /> },
      { path: 'profile', element: <ProfilePage /> },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);