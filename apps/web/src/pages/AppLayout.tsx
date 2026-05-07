import { useEffect } from "react";
import { Link, Outlet } from "react-router-dom";
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

  return (
    <div className="min-h-screen">
      <nav className="bg-white border-b p-4 flex gap-4 items-center">
        <Link to="/">Dashboard</Link>
        <Link to="/tasks/new">Créer</Link>
        <Link to="/tasks">Tâches</Link>
        <Link to="/wallet">Wallet</Link>
        <Link to="/profile">Profil</Link>
        <div className="ml-auto flex items-center gap-3">
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
