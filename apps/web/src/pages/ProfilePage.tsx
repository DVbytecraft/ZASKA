import { useEffect, useState } from "react";
import { useAuthStore } from "../store";
import { api } from "../api";

interface WalletBalance {
  currency: string;
  balance: string;
}

export function ProfilePage() {
  const { profile, loadProfile } = useAuthStore();
  const [wallets, setWallets] = useState<WalletBalance[]>([]);
  const [walletsLoading, setWalletsLoading] = useState(true);

  useEffect(() => {
    void loadProfile();
    (async () => {
      const [usd, xof] = await Promise.all([
        api.getWalletBalance("USD"),
        api.getWalletBalance("XOF"),
      ]);
      const result: WalletBalance[] = [];
      if (usd.success) result.push(usd.data);
      if (xof.success) result.push(xof.data);
      setWallets(result);
      setWalletsLoading(false);
    })();
  }, []);

  if (!profile) {
    return <p className="text-sm text-gray-400">Chargement du profil...</p>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Mon profil</h2>

      <div className="bg-white border rounded-xl p-5 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="text-xs text-gray-500 mb-0.5">Prénom</p>
            <p className="text-sm font-medium">{profile.first_name ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-0.5">Nom</p>
            <p className="text-sm font-medium">{profile.last_name ?? "—"}</p>
          </div>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Email</p>
          <p className="text-sm font-medium">{profile.email}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Téléphone</p>
          <p className="text-sm font-medium">{profile.phone ?? "—"}</p>
        </div>
        <div className="flex items-center gap-4">
          <div>
            <p className="text-xs text-gray-500 mb-0.5">Rôle</p>
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 font-medium capitalize">
              {profile.role}
            </span>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-0.5">Compte</p>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                profile.is_verified
                  ? "bg-green-100 text-green-700"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {profile.is_verified ? "Vérifié" : "Non vérifié"}
            </span>
          </div>
          {profile.country_code && (
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Pays</p>
              <p className="text-sm font-medium">{profile.country_code}</p>
            </div>
          )}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-2">Portefeuilles</h3>
        {walletsLoading ? (
          <p className="text-sm text-gray-400">Chargement...</p>
        ) : wallets.length === 0 ? (
          <p className="text-sm text-gray-400">Aucun portefeuille.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {wallets.map((w) => (
              <div key={w.currency} className="bg-white border rounded-xl p-4">
                <p className="text-xs text-gray-500 mb-1">{w.currency}</p>
                <p className="text-2xl font-bold">{parseFloat(w.balance).toFixed(2)}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
