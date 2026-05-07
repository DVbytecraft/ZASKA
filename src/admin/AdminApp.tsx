import { useState } from 'react';
import { AdminLayout } from './components/AdminLayout';
import { DashboardPage } from './pages/DashboardPage';
import { TasksPage } from './pages/TasksPage';
import { UsersPage } from './pages/UsersPage';
import { TaskersPage } from './pages/TaskersPage';
import { PaymentsPage } from './pages/PaymentsPage';
import { DisputesPage } from './pages/DisputesPage';
import { CallCenterPage } from './pages/CallCenterPage';
import { CountriesPage } from './pages/CountriesPage';

export function AdminApp() {
  const [activePage, setActivePage] = useState('dashboard');

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard':
        return <DashboardPage />;
      case 'tasks':
        return <TasksPage />;
      case 'users':
        return <UsersPage />;
      case 'taskers':
        return <TaskersPage />;
      case 'payments':
        return <PaymentsPage />;
      case 'disputes':
        return <DisputesPage />;
      case 'callcenter':
        return <CallCenterPage />;
      case 'countries':
        return <CountriesPage />;
      case 'settings':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Settings</h2>
            <p className="text-gray-600">Platform settings and configuration.</p>
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
