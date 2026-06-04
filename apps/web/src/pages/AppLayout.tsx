import { useEffect } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuthStore } from "../store";

export function AppLayout() {
  const logout = useAuthStore((s) => s.logout);
  const profile = useAuthStore((s) => s.profile);
  const loadProfile = useAuthStore((s) => s.loadProfile);

  useEffect(() => {
    void loadProfile();
  }, []);

  const displayName = profile
    ? `${profile.first_name ?? ""} ${profile.last_name ?? ""}`.trim() || profile.email
    : null;

  const navLink = (to: string, label: string) => (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `text-sm font-medium transition-colors ${isActive ? "text-gray-900 underline underline-offset-4" : "text-gray-500 hover:text-gray-800"}`
      }
    >
      {label}
    </NavLink>
  );

  return (
    <div className="min-h-screen">
      <nav className="bg-white border-b p-4 flex gap-4 items-center overflow-x-auto">
        {navLink("/", "Dashboard")}
        {navLink("/tasks/new", "Créer")}
        {navLink("/tasks", "Tâches")}
        {navLink("/wallet", "Wallet")}
        {navLink("/profile", "Profil")}
        <div className="ml-auto flex items-center gap-3 flex-shrink-0">
          {displayName && (
            <span className="text-sm text-gray-600 font-medium">{displayName}</span>
          )}
          <button
            className="bg-black text-white px-3 py-1 rounded text-sm"
            onClick={() => void logout()}
          >
            Déconnexion
          </button>
        </div>
      </nav>
      <main className="p-6 max-w-3xl mx-auto">
        <Outlet />
      </main>
    </div>
  );
}
