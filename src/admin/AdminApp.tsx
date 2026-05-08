import { useState } from 'react';
import { AdminLayout } from './components/AdminLayout';
import { DashboardPage } from './pages/DashboardPage';
import { TasksPage } from './pages/TasksPage';
import { UsersPage } from './pages/UsersPage';
import { TaskersPage } from './pages/TaskersPage';
import { PaymentsPage } from './pages/PaymentsPage';
import { WalletPage } from './pages/WalletPage';
import { DisputesPage } from './pages/DisputesPage';
import { CallCenterPage } from './pages/CallCenterPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { CountriesPage } from './pages/CountriesPage';
import { KycReviewPage } from './pages/KycReviewPage';
import { AuditLogPage } from './pages/AuditLogPage';
import { FraudFlagsPage } from './pages/FraudFlagsPage';

export function AdminApp() {
  const [activePage, setActivePage] = useState('dashboard');

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard':   return <DashboardPage />;
      case 'tasks':       return <TasksPage />;
      case 'users':       return <UsersPage />;
      case 'taskers':     return <TaskersPage />;
      case 'payments':    return <PaymentsPage />;
      case 'wallet':      return <WalletPage />;
      case 'disputes':    return <DisputesPage />;
      case 'analytics':   return <AnalyticsPage />;
      case 'callcenter':  return <CallCenterPage />;
      case 'countries':   return <CountriesPage />;
      case 'kyc':         return <KycReviewPage />;
      case 'auditlog':    return <AuditLogPage />;
      case 'fraud':       return <FraudFlagsPage />;
      case 'settings':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Paramètres</h2>
            <p className="text-gray-600">Configuration de la plateforme.</p>
          </div>
        );
      default:
        return <DashboardPage />;
    }
  };

  return (
    <AdminLayout activePage={activePage} onNavigate={setActivePage}>
      {renderPage()}
    </AdminLayout>
  );
}
