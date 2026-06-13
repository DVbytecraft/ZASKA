import { useEffect, useState } from "react";
import { useAuthStore } from "../store";
import { api, type KycStatus } from "../api";

interface WalletBalance {
  currency: string;
  balance: string;
}

export function ProfilePage() {
  const { profile, loadProfile } = useAuthStore();
  const [wallets, setWallets] = useState<WalletBalance[]>([]);
  const [walletsLoading, setWalletsLoading] = useState(true);
  const [kycStatus, setKycStatus] = useState<KycStatus | null>(null);
  const [kycLoading, setKycLoading] = useState(true);

  useEffect(() => {
    void loadProfile();
    (async () => {
      const [usd, xof, kyc] = await Promise.all([
        api.getWalletBalance("USD"),
        api.getWalletBalance("XOF"),
        api.getKycStatus(),
      ]);
      const result: WalletBalance[] = [];
      if (usd.success) result.push(usd.data);
      if (xof.success) result.push(xof.data);
      setWallets(result);
      setWalletsLoading(false);
      if (kyc.success) setKycStatus(kyc.data);
      setKycLoading(false);
    })();
  }, [loadProfile]);

  const kycTone =
    kycStatus?.status === "approved" && !kycStatus?.isExpired
      ? "bg-green-100 text-green-700"
      : kycStatus?.isExpired
        ? "bg-red-100 text-red-700"
        : kycStatus?.status === "pending"
          ? "bg-amber-100 text-amber-700"
          : "bg-gray-100 text-gray-700";

  const kycLabel =
    kycStatus?.status === "approved" && !kycStatus?.isExpired
      ? "KYC actif"
      : kycStatus?.isExpired
        ? "KYC expire"
        : kycStatus?.status === "pending"
          ? "KYC en revue"
          : "KYC a soumettre";

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

      <div className="bg-white border rounded-xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Conformite & securite</h3>
            <p className="text-sm text-gray-500">
              Etat du KYC, biometrie et controle de securite pour votre compte.
            </p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${kycTone}`}>
            {kycLoading ? "Chargement..." : kycLabel}
          </span>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-xl bg-gray-50 p-4">
            <p className="text-xs text-gray-500 mb-1">Expiration KYC</p>
            <p className="text-sm font-medium">
              {kycStatus?.expiresAt
                ? new Date(kycStatus.expiresAt).toLocaleDateString("fr-FR")
                : "Non disponible"}
            </p>
            {typeof kycStatus?.daysRemaining === "number" && (
              <p className="mt-1 text-xs text-gray-500">
                {kycStatus.daysRemaining >= 0
                  ? `${kycStatus.daysRemaining} jour(s) restants`
                  : "Renouvellement requis immediatement"}
              </p>
            )}
          </div>
          <div className="rounded-xl bg-gray-50 p-4">
            <p className="text-xs text-gray-500 mb-1">Verification tasker</p>
            <p className="text-sm font-medium">
              {profile.tasker_security_verified ? "Validee" : "En attente"}
            </p>
            <p className="mt-1 text-xs text-gray-500">
              {profile.biometric_enabled ? "Biometrie activee" : "Biometrie non activee"}
              {profile.criminal_record_status
                ? ` • Casier: ${profile.criminal_record_status}`
                : ""}
            </p>
          </div>
        </div>

        {kycStatus?.reviewerNote && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
              Note de revue
            </p>
            <p className="mt-1 text-sm text-amber-900">{kycStatus.reviewerNote}</p>
          </div>
        )}
      </div>

      <div className="bg-white border rounded-xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Badges Zaska</h3>
            <p className="text-sm text-gray-500">
              Visibilite publique de confiance, conformité et ancienneté.
            </p>
          </div>
          {profile.trustScore && (
            <span className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-700">
              {profile.trustScore.level} · {profile.trustScore.totalScore}/100
            </span>
          )}
        </div>

        {!profile.badges || profile.badges.length === 0 ? (
          <p className="text-sm text-gray-400">Aucun badge disponible pour le moment.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {profile.badges.map((badge) => (
              <div key={badge.code} className="rounded-xl border bg-gray-50 px-3 py-2">
                <p className="text-sm font-semibold text-gray-900">{badge.label}</p>
                <p className="text-xs text-gray-500">{badge.description}</p>
              </div>
            ))}
          </div>
        )}
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
