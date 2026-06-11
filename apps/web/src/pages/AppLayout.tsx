import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api";
import { useAuthStore } from "../store";

export function AppLayout() {
  const logout = useAuthStore((s) => s.logout);
  const profile = useAuthStore((s) => s.profile);
  const loadProfile = useAuthStore((s) => s.loadProfile);
  const [unreadCount, setUnreadCount] = useState(0);
  const location = useLocation();

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  useEffect(() => {
    let active = true;

    const refreshUnreadCount = async () => {
      const res = await api.getUnreadNotificationsCount();
      if (active && res.success) {
        setUnreadCount(res.data.count);
      }
    };

    void refreshUnreadCount();
    const intervalId = window.setInterval(() => {
      void refreshUnreadCount();
    }, 30000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [location.pathname, profile?.id]);

  const displayName = profile
    ? `${profile.first_name ?? ""} ${profile.last_name ?? ""}`.trim() || profile.email
    : null;

  const navLink = (to: string, label: string, badgeCount?: number) => (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-2 whitespace-nowrap text-sm font-medium transition-colors ${
          isActive ? "text-gray-900 underline underline-offset-4" : "text-gray-500 hover:text-gray-800"
        }`
      }
    >
      {label}
      {badgeCount && badgeCount > 0 ? (
        <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-semibold text-white">
          {badgeCount > 99 ? "99+" : badgeCount}
        </span>
      ) : null}
    </NavLink>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b bg-white p-4">
        <div className="mx-auto flex max-w-7xl items-center gap-4 overflow-x-auto">
          {navLink("/", "Dashboard")}
          {navLink("/marketplace", "Explorer")}
          {navLink("/food", "Manger")}
          {navLink("/shop", "Articles")}
          {navLink("/vtc", "VTC")}
          {navLink("/tasks/new", "Créer")}
          {navLink("/tasks", "Tâches")}
          {navLink("/wallet", "Wallet")}
          {profile?.role === "tasker" && navLink("/social-protection", "Mon capital")}
          {profile?.role === "tasker" && navLink("/vtc/driver", "Courses")}
          {navLink("/notifications", "Notifications", unreadCount)}
          {navLink("/profile", "Profil")}
          <div className="ml-auto flex flex-shrink-0 items-center gap-3">
            {displayName ? <span className="text-sm font-medium text-gray-600">{displayName}</span> : null}
            <button
              className="rounded bg-black px-3 py-1 text-sm text-white"
              onClick={() => void logout()}
            >
              Déconnexion
            </button>
          </div>
        </div>
      </nav>
      <main className="mx-auto max-w-7xl p-6">
        <Outlet />
      </main>
    </div>
  );
}
