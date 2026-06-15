import { useEffect, useState } from 'react';
import { Plus, X, Loader2, UserCog } from 'lucide-react';
import { DataTable } from '../components/DataTable';
import { adminApi, type AdminStaffAccount, type AdminRole } from '../adminApi';

const ROLE_LABEL_FALLBACK: Record<string, string> = {
  platform_admin: 'Administrateur plateforme',
  finance_admin: 'Administrateur finance',
  operations_manager: 'Responsable opérations',
  accountant: 'Comptable',
  call_center_agent: 'Agent call center',
  kyc_agent: 'Agent KYC',
  moderator: 'Modérateur',
};

function CreateStaffModal({ roles, onClose, onCreated }: {
  roles: AdminRole[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [phone, setPhone] = useState('');
  const [countryCode, setCountryCode] = useState('');
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleRole = (code: string) => {
    setSelectedRoles((prev) => prev.includes(code) ? prev.filter((r) => r !== code) : [...prev, code]);
  };

  const canSubmit = email.trim() && password.trim().length >= 8 && firstName.trim() && lastName.trim() && selectedRoles.length > 0;

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await adminApi.createStaffAccount({
        email: email.trim(),
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        role_codes: selectedRoles,
        country_code: countryCode.trim() || null,
        phone: phone.trim() || null,
      });
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de la création du compte');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg border border-gray-200 max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between p-6 pb-4">
          <div>
            <h3 className="text-base font-bold text-gray-900">Nouveau compte staff</h3>
            <p className="text-sm text-gray-600 mt-1">Créer un compte administratif (comptable, call center, modérateur...)</p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600 transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="px-6 pb-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Prénom</label>
              <input value={firstName} onChange={(e) => setFirstName(e.target.value)} className="w-full px-3 py-2.5 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Nom</label>
              <input value={lastName} onChange={(e) => setLastName(e.target.value)} className="w-full px-3 py-2.5 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full px-3 py-2.5 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm" />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Mot de passe (min. 8 caractères)</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full px-3 py-2.5 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Téléphone (optionnel)</label>
              <input value={phone} onChange={(e) => setPhone(e.target.value)} className="w-full px-3 py-2.5 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Pays (code, optionnel)</label>
              <input value={countryCode} onChange={(e) => setCountryCode(e.target.value.toUpperCase())} placeholder="CI, SN, NG..." className="w-full px-3 py-2.5 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              Rôles <span className="text-red-500">*</span>
            </label>
            <div className="space-y-2">
              {roles.map((role) => (
                <label key={role.code} className="flex items-start gap-3 p-3 rounded-xl border border-gray-200 hover:bg-gray-50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={selectedRoles.includes(role.code)}
                    onChange={() => toggleRole(role.code)}
                    className="mt-0.5 accent-[#6D28D9]"
                  />
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{role.label || ROLE_LABEL_FALLBACK[role.code] || role.code}</p>
                    <p className="text-xs text-gray-500">{role.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg p-3">{error}</p>}
        </div>

        <div className="px-6 pb-6 flex gap-3 justify-end">
          <button onClick={onClose} disabled={submitting} className="px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors">
            Annuler
          </button>
          <button
            onClick={submit}
            disabled={!canSubmit || submitting}
            className="px-5 py-2.5 rounded-xl text-sm font-bold text-white transition-colors flex items-center gap-2 bg-[#6D28D9] hover:bg-[#5B21B6] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Créer le compte
          </button>
        </div>
      </div>
    </div>
  );
}

export function StaffPage() {
  const [staff, setStaff] = useState<AdminStaffAccount[]>([]);
  const [roles, setRoles] = useState<AdminRole[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const load = () => {
    setLoading(true);
    Promise.all([adminApi.getStaffAccounts(), adminApi.getRoleCatalog()])
      .then(([staffData, roleData]) => {
        setStaff(staffData);
        setRoles(roleData.roles);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Erreur de chargement'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const roleLabel = (code: string) => {
    const role = roles.find((r) => r.code === code);
    return role?.label || ROLE_LABEL_FALLBACK[code] || code;
  };

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Équipe</h2>
          <p className="text-sm text-gray-600">Comptes administratifs : comptables, call center, modérateurs...</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-[#6D28D9] hover:bg-[#5B21B6] transition-colors flex-shrink-0"
        >
          <Plus size={16} />
          Nouveau compte
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Chargement...</p>
      ) : error ? (
        <p className="text-red-600 text-sm bg-red-50 rounded-lg p-4">{error}</p>
      ) : staff.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
          <UserCog size={32} className="mx-auto text-gray-300 mb-2" />
          <p className="text-sm text-gray-500">Aucun compte staff pour l'instant.</p>
        </div>
      ) : (
        <DataTable
          columns={[
            { key: 'full_name', label: 'Nom', render: (v, row) => (v as string | null) || `${(row as AdminStaffAccount).first_name ?? ''} ${(row as AdminStaffAccount).last_name ?? ''}`.trim() || '—' },
            { key: 'email', label: 'Email', render: (v) => (v as string | null) ?? '—' },
            { key: 'roles', label: 'Rôles', render: (v) => (
              <div className="flex flex-wrap gap-1">
                {(v as string[]).map((code) => (
                  <span key={code} className="px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                    {roleLabel(code)}
                  </span>
                ))}
              </div>
            )},
            { key: 'country_code', label: 'Pays', render: (v) => (v as string | null) ?? '—' },
            { key: 'is_suspended', label: 'Statut', render: (v) => (
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${v ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                {v ? 'Suspendu' : 'Actif'}
              </span>
            )},
          ]}
          data={staff}
        />
      )}

      {showCreate && (
        <CreateStaffModal
          roles={roles}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(); }}
        />
      )}
    </div>
  );
}
