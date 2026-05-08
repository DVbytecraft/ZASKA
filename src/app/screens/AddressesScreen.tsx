import { useEffect, useState } from 'react';
import { ArrowLeft, Plus, MapPin, Star, Trash2, Edit2, Navigation, Loader, AlertCircle, Check } from 'lucide-react';
import { apiClient } from '@zaska/shared-services';
import type { UserAddress } from '@zaska/shared-services';
import { requestGeolocation } from '../hooks/useTaskFlow';

interface AddressesScreenProps {
  onBack: () => void;
}

interface AddressFormData {
  label: string;
  street: string;
  city: string;
  country: string;
  latitude: number | null;
  longitude: number | null;
  isDefault: boolean;
}

const LABEL_PRESETS = ['Maison', 'Bureau', 'École', 'Salle de sport', 'Autre'];

const emptyForm = (): AddressFormData => ({
  label: '',
  street: '',
  city: '',
  country: '',
  latitude: null,
  longitude: null,
  isDefault: false,
});

interface AddressFormProps {
  initial?: AddressFormData;
  onSave: (data: AddressFormData) => Promise<void>;
  onClose: () => void;
  saving: boolean;
  error: string | null;
}

function AddressForm({ initial, onSave, onClose, saving, error }: AddressFormProps) {
  const [form, setForm] = useState<AddressFormData>(initial ?? emptyForm());
  const [gpsLoading, setGpsLoading] = useState(false);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [customLabel, setCustomLabel] = useState(
    initial?.label && !LABEL_PRESETS.includes(initial.label) ? initial.label : ''
  );
  const [useCustom, setUseCustom] = useState(
    !!initial?.label && !LABEL_PRESETS.includes(initial.label)
  );

  const effectiveLabel = useCustom ? customLabel : form.label;
  const isValid = effectiveLabel.trim() && form.street.trim() && form.city.trim() && form.country.trim();

  const handleGps = () => {
    setGpsLoading(true);
    setGpsError(null);
    requestGeolocation()
      .then(({ latitude, longitude }) => {
        setForm(f => ({ ...f, latitude, longitude }));
        setGpsLoading(false);
      })
      .catch(() => {
        setGpsError('Géolocalisation refusée');
        setGpsLoading(false);
      });
  };

  const handleSubmit = () => {
    if (!isValid) return;
    onSave({ ...form, label: effectiveLabel.trim() });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-end" onClick={onClose}>
      <div
        className="w-full bg-white rounded-t-3xl max-h-[90vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-lg font-bold text-gray-900">
            {initial ? 'Modifier l\'adresse' : 'Nouvelle adresse'}
          </h3>
          <button onClick={onClose} className="text-gray-400 font-bold text-xl leading-none">✕</button>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-4 space-y-4">
          {/* Label presets */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Libellé</label>
            <div className="flex flex-wrap gap-2 mb-2">
              {LABEL_PRESETS.map(preset => (
                <button
                  key={preset}
                  onClick={() => {
                    if (preset === 'Autre') {
                      setUseCustom(true);
                      setForm(f => ({ ...f, label: '' }));
                    } else {
                      setUseCustom(false);
                      setForm(f => ({ ...f, label: preset }));
                    }
                  }}
                  className={`px-3 py-1.5 rounded-xl text-sm font-semibold border-2 transition-all ${
                    (!useCustom && form.label === preset) || (useCustom && preset === 'Autre')
                      ? 'border-[#6D28D9] bg-purple-50 text-[#6D28D9]'
                      : 'border-gray-100 bg-gray-50 text-gray-600'
                  }`}
                >
                  {preset}
                </button>
              ))}
            </div>
            {useCustom && (
              <input
                type="text"
                placeholder="Mon libellé personnalisé"
                value={customLabel}
                onChange={e => setCustomLabel(e.target.value)}
                autoFocus
                className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-gray-900"
              />
            )}
          </div>

          {/* Street */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Rue / Quartier</label>
            <input
              type="text"
              placeholder="Ex : Rue de la Paix, Quartier Bè"
              value={form.street}
              onChange={e => setForm(f => ({ ...f, street: e.target.value }))}
              className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-gray-900"
            />
          </div>

          {/* City + Country */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Ville</label>
              <input
                type="text"
                placeholder="Lomé"
                value={form.city}
                onChange={e => setForm(f => ({ ...f, city: e.target.value }))}
                className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-gray-900"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Pays</label>
              <input
                type="text"
                placeholder="Togo"
                value={form.country}
                onChange={e => setForm(f => ({ ...f, country: e.target.value }))}
                className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-gray-900"
              />
            </div>
          </div>

          {/* GPS coordinates */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Coordonnées GPS <span className="text-gray-400 font-normal normal-case">(optionnel — améliore la précision)</span>
            </label>
            <button
              onClick={handleGps}
              disabled={gpsLoading}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border-2 transition-all ${
                form.latitude
                  ? 'border-green-300 bg-green-50'
                  : 'border-gray-200 hover:border-[#6D28D9] hover:bg-purple-50'
              }`}
            >
              {gpsLoading ? (
                <Loader size={18} className="text-[#6D28D9] animate-spin shrink-0" />
              ) : form.latitude ? (
                <Check size={18} className="text-green-600 shrink-0" />
              ) : (
                <Navigation size={18} className="text-gray-400 shrink-0" />
              )}
              <span className={`text-sm font-medium ${form.latitude ? 'text-green-700' : 'text-gray-600'}`}>
                {form.latitude
                  ? `${form.latitude.toFixed(4)}, ${form.longitude?.toFixed(4)}`
                  : 'Utiliser ma position GPS'}
              </span>
            </button>
            {gpsError && <p className="text-xs text-red-500 mt-1">{gpsError}</p>}
          </div>

          {/* Default toggle */}
          <label className="flex items-center gap-3 cursor-pointer">
            <div
              onClick={() => setForm(f => ({ ...f, isDefault: !f.isDefault }))}
              className={`w-12 h-6 rounded-full transition-colors ${form.isDefault ? 'bg-[#6D28D9]' : 'bg-gray-300'}`}
            >
              <div className={`w-5 h-5 bg-white rounded-full shadow transition-transform mt-0.5 ${form.isDefault ? 'ml-6' : 'ml-0.5'}`} />
            </div>
            <span className="text-sm font-medium text-gray-700">Adresse par défaut</span>
          </label>

          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
              <AlertCircle size={15} className="text-red-500 shrink-0" />
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}
        </div>

        <div className="px-6 pb-8 pt-3 border-t border-gray-100">
          <button
            onClick={handleSubmit}
            disabled={!isValid || saving}
            className="w-full py-4 rounded-xl font-bold text-base text-white transition-all"
            style={{
              background: isValid && !saving
                ? 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)'
                : '#D1D5DB',
            }}
          >
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────
export function AddressesScreen({ onBack }: AddressesScreenProps) {
  const [addresses, setAddresses] = useState<UserAddress[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editAddress, setEditAddress] = useState<UserAddress | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setLoadError(null);
    apiClient
      .get<UserAddress[]>('/addresses')
      .then(setAddresses)
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Erreur de chargement'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSave = async (data: AddressFormData) => {
    setSaving(true);
    setSaveError(null);
    try {
      if (editAddress) {
        const updated = await apiClient.patch<UserAddress>(`/addresses/${editAddress.id}`, {
          label: data.label,
          street: data.street,
          city: data.city,
          country: data.country,
          latitude: data.latitude,
          longitude: data.longitude,
          is_default: data.isDefault,
        });
        setAddresses(prev =>
          prev.map(a => a.id === editAddress.id ? updated : data.isDefault ? { ...a, isDefault: false } : a)
        );
      } else {
        const created = await apiClient.post<UserAddress>('/addresses', {
          label: data.label,
          street: data.street,
          city: data.city,
          country: data.country,
          latitude: data.latitude,
          longitude: data.longitude,
          is_default: data.isDefault,
        });
        setAddresses(prev =>
          data.isDefault
            ? [created, ...prev.map(a => ({ ...a, isDefault: false }))]
            : [...prev, created]
        );
      }
      setShowForm(false);
      setEditAddress(null);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Erreur lors de l\'enregistrement');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await apiClient.delete<{ deleted: boolean }>(`/addresses/${id}`);
      setAddresses(prev => prev.filter(a => a.id !== id));
    } catch {
      // silently ignore; could show toast
    } finally {
      setDeleting(null);
    }
  };

  const openEdit = (addr: UserAddress) => {
    setEditAddress(addr);
    setSaveError(null);
    setShowForm(true);
  };

  const openAdd = () => {
    setEditAddress(null);
    setSaveError(null);
    setShowForm(true);
  };

  const toFormData = (addr: UserAddress): AddressFormData => ({
    label: addr.label,
    street: addr.street,
    city: addr.city,
    country: addr.country,
    latitude: addr.latitude,
    longitude: addr.longitude,
    isDefault: addr.isDefault,
  });

  return (
    <div className="h-full flex flex-col bg-gray-50" style={{ fontFamily: "'Poppins', sans-serif" }}>
      {showForm && (
        <AddressForm
          initial={editAddress ? toFormData(editAddress) : undefined}
          onSave={handleSave}
          onClose={() => { setShowForm(false); setEditAddress(null); }}
          saving={saving}
          error={saveError}
        />
      )}

      {/* Header */}
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
              <ArrowLeft size={24} className="text-gray-700" />
            </button>
            <div>
              <h2 className="text-xl font-bold text-gray-900">Mes adresses</h2>
              <p className="text-xs text-gray-400">Adresses enregistrées</p>
            </div>
          </div>
          <button
            onClick={openAdd}
            className="flex items-center gap-1.5 px-4 py-2 bg-purple-50 text-[#6D28D9] rounded-xl font-semibold text-sm"
          >
            <Plus size={16} />
            Ajouter
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {loadError && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2 mb-4">
            <AlertCircle size={16} className="text-red-500 shrink-0" />
            <p className="text-sm text-red-600 flex-1">{loadError}</p>
            <button onClick={load} className="text-xs font-semibold text-red-600 underline">Réessayer</button>
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => <div key={i} className="h-24 bg-white rounded-2xl animate-pulse" />)}
          </div>
        ) : addresses.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-52 text-center">
            <div className="w-16 h-16 bg-purple-100 rounded-2xl flex items-center justify-center mb-4">
              <MapPin size={28} className="text-[#6D28D9]" />
            </div>
            <p className="font-semibold text-gray-700 mb-1">Aucune adresse enregistrée</p>
            <p className="text-sm text-gray-400 mb-4">Ajoutez votre domicile, bureau ou tout lieu fréquent</p>
            <button
              onClick={openAdd}
              className="px-6 py-2.5 bg-purple-50 text-[#6D28D9] rounded-xl font-semibold text-sm"
            >
              Ajouter une adresse
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {addresses.map(addr => (
              <div key={addr.id} className="bg-white rounded-2xl p-4 shadow-sm">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl bg-purple-50 flex items-center justify-center shrink-0 mt-0.5">
                    <MapPin size={18} className="text-[#6D28D9]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <p className="font-bold text-gray-900 text-sm">{addr.label}</p>
                      {addr.isDefault && (
                        <span className="flex items-center gap-1 text-xs text-amber-600 font-semibold">
                          <Star size={10} className="fill-amber-400 text-amber-400" /> Par défaut
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 truncate">{addr.street}</p>
                    <p className="text-xs text-gray-400">{addr.city}, {addr.country}</p>
                    {addr.latitude && (
                      <p className="text-xs text-green-600 mt-0.5">
                        GPS enregistré
                      </p>
                    )}
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button
                      onClick={() => openEdit(addr)}
                      className="w-8 h-8 rounded-xl bg-gray-50 flex items-center justify-center text-gray-500 hover:bg-purple-50 hover:text-[#6D28D9] transition-colors"
                    >
                      <Edit2 size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(addr.id)}
                      disabled={deleting === addr.id}
                      className="w-8 h-8 rounded-xl bg-gray-50 flex items-center justify-center text-red-400 hover:bg-red-50 transition-colors"
                    >
                      {deleting === addr.id ? (
                        <Loader size={14} className="animate-spin" />
                      ) : (
                        <Trash2 size={14} />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
