import { useEffect, useRef, useState } from 'react';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { ArrowLeft, MapPin, Loader, AlertCircle, Navigation, Plus, X, GripVertical, Calendar, Clock, Infinity } from 'lucide-react';
import { useTaskFlow, requestGeolocation } from '../hooks/useTaskFlow';
import { paymentService, apiClient } from '@zaska/shared-services';
import type { TaskMode, TaskStop, UserAddress } from '@zaska/shared-services';

interface PostTaskScreenProps {
  taskMode: TaskMode;
  onBack: () => void;
  onSubmit: (taskId: string) => void;
}

interface GeoResult {
  lat: number;
  lng: number;
  city: string;
  country: string;
  display: string;
}

async function geocodeAndResolve(query: string): Promise<GeoResult | null> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=1&addressdetails=1`,
      { headers: { 'Accept-Language': 'fr,en' } }
    );
    const data = await res.json();
    if (Array.isArray(data) && data.length > 0) {
      const item = data[0];
      const addr = item.address ?? {};
      const city = addr.city ?? addr.town ?? addr.village ?? addr.county ?? query;
      const country = addr.country ?? '';
      const display = [city, country].filter(Boolean).join(', ') || query;
      return { lat: parseFloat(item.lat), lng: parseFloat(item.lon), city, country, display };
    }
  } catch {
    // ignore
  }
  return null;
}

async function reverseGeocode(lat: number, lng: number): Promise<{ address: string; city: string; country: string } | null> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`,
      { headers: { 'Accept-Language': 'fr,en' } }
    );
    const data = await res.json();
    if (data?.address) {
      const addr = data.address;
      const city = addr.city ?? addr.town ?? addr.village ?? addr.county ?? '';
      const country = addr.country ?? '';
      const address = [city, country].filter(Boolean).join(', ') || data.display_name || 'Position GPS';
      return { address, city, country };
    }
  } catch {
    // ignore
  }
  return null;
}

// ── Stop picker bottom drawer ─────────────────────────────────────────────────
interface StopPickerProps {
  savedAddresses: UserAddress[];
  onConfirm: (stop: TaskStop, city?: string, country?: string) => void;
  onClose: () => void;
}

function StopPicker({ savedAddresses, onConfirm, onClose }: StopPickerProps) {
  const [mode, setMode] = useState<'menu' | 'gps' | 'manual'>('menu');
  const [gpsLoading, setGpsLoading] = useState(false);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [manualCity, setManualCity] = useState('');
  const [geocoding, setGeocoding] = useState(false);
  const [geocodeError, setGeocodeError] = useState<string | null>(null);

  const handleGps = () => {
    setMode('gps');
    setGpsLoading(true);
    setGpsError(null);
    requestGeolocation()
      .then(async ({ latitude, longitude }) => {
        const geo = await reverseGeocode(latitude, longitude);
        onConfirm(
          { address: geo?.address ?? 'Position GPS', latitude, longitude },
          geo?.city,
          geo?.country,
        );
      })
      .catch(() => {
        setGpsError('Géolocalisation refusée. Activez-la dans les paramètres.');
        setGpsLoading(false);
      });
  };

  const handleSaved = (addr: UserAddress) => {
    if (!addr.latitude || !addr.longitude) return;
    onConfirm(
      { address: `${addr.label} · ${addr.city}`, latitude: addr.latitude, longitude: addr.longitude },
      addr.city || undefined,
      addr.country || undefined,
    );
  };

  const handleGeocode = async () => {
    if (!manualCity.trim()) return;
    setGeocoding(true);
    setGeocodeError(null);
    const result = await geocodeAndResolve(manualCity.trim());
    setGeocoding(false);
    if (result) {
      onConfirm(
        { address: result.display, latitude: result.lat, longitude: result.lng },
        result.city,
        result.country,
      );
    } else {
      setGeocodeError(`Ville introuvable : "${manualCity}". Essayez un nom plus précis.`);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-end" onClick={onClose}>
      <div
        className="w-full bg-white rounded-t-3xl max-h-[80vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between">
          {mode !== 'menu' ? (
            <button onClick={() => { setMode('menu'); setGpsError(null); setGeocodeError(null); }} className="text-[#6D28D9] font-semibold text-sm">← Retour</button>
          ) : <div />}
          <h3 className="text-base font-bold text-gray-900">Ajouter un point d'arrêt</h3>
          <button onClick={onClose} className="text-gray-400 font-bold text-xl leading-none">✕</button>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-4">
          {mode === 'menu' && (
            <div className="space-y-3">
              {/* GPS */}
              <button
                onClick={handleGps}
                className="w-full flex items-center gap-4 p-4 rounded-2xl border-2 border-gray-100 hover:border-[#6D28D9] hover:bg-purple-50 transition-all text-left"
              >
                <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center shrink-0">
                  <Navigation size={20} className="text-blue-600" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900 text-sm">Ma position actuelle</p>
                  <p className="text-xs text-gray-400">Utiliser le GPS</p>
                </div>
              </button>

              {/* Manual city */}
              <button
                onClick={() => setMode('manual')}
                className="w-full flex items-center gap-4 p-4 rounded-2xl border-2 border-gray-100 hover:border-[#6D28D9] hover:bg-purple-50 transition-all text-left"
              >
                <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center shrink-0">
                  <MapPin size={20} className="text-green-600" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900 text-sm">Entrer une ville</p>
                  <p className="text-xs text-gray-400">Recherche par nom</p>
                </div>
              </button>

              {/* Saved addresses */}
              {savedAddresses.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 mt-2">Adresses enregistrées</p>
                  <div className="space-y-2">
                    {savedAddresses
                      .filter(a => a.latitude && a.longitude)
                      .map(addr => (
                        <button
                          key={addr.id}
                          onClick={() => handleSaved(addr)}
                          className="w-full flex items-center gap-3 p-3 rounded-xl border border-gray-100 hover:border-[#6D28D9] hover:bg-purple-50 transition-all text-left"
                        >
                          <div className="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center shrink-0">
                            <MapPin size={14} className="text-[#6D28D9]" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-semibold text-gray-900 text-sm truncate">{addr.label}</p>
                            <p className="text-xs text-gray-400 truncate">{addr.city}</p>
                          </div>
                          {addr.isDefault && (
                            <span className="text-xs text-[#6D28D9] font-semibold shrink-0">Par défaut</span>
                          )}
                        </button>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {mode === 'gps' && (
            <div className="flex flex-col items-center justify-center py-12">
              {gpsLoading ? (
                <>
                  <Loader size={32} className="text-[#6D28D9] animate-spin mb-4" />
                  <p className="text-sm text-gray-500">Récupération de la position…</p>
                </>
              ) : gpsError ? (
                <>
                  <AlertCircle size={32} className="text-red-400 mb-3" />
                  <p className="text-sm text-red-600 text-center">{gpsError}</p>
                  <button onClick={handleGps} className="mt-4 text-sm text-[#6D28D9] font-semibold underline">Réessayer</button>
                </>
              ) : null}
            </div>
          )}

          {mode === 'manual' && (
            <div>
              <p className="text-sm text-gray-500 mb-3">Entrez le nom d'une ville ou d'un quartier</p>
              <input
                type="text"
                placeholder="Ex : Lomé, Cotonou, Abidjan…"
                value={manualCity}
                onChange={e => { setManualCity(e.target.value); setGeocodeError(null); }}
                onKeyDown={e => e.key === 'Enter' && handleGeocode()}
                autoFocus
                className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-gray-900"
              />
              {geocodeError && (
                <p className="text-xs text-red-500 mt-2 flex items-center gap-1">
                  <AlertCircle size={13} /> {geocodeError}
                </p>
              )}
              <button
                onClick={handleGeocode}
                disabled={!manualCity.trim() || geocoding}
                className="mt-3 w-full py-3 rounded-xl font-semibold text-white transition-all"
                style={{ background: manualCity.trim() && !geocoding ? 'linear-gradient(135deg,#6D28D9,#7C3AED)' : '#D1D5DB' }}
              >
                {geocoding ? <span className="flex items-center justify-center gap-2"><Loader size={16} className="animate-spin" /> Recherche…</span> : 'Confirmer'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────
export function PostTaskScreen({ taskMode, onBack, onSubmit }: PostTaskScreenProps) {
  const [step, setStep] = useState(1);
  const [description, setDescription] = useState('');
  const [budget, setBudget] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { createTask, loading } = useTaskFlow();
  // Stable idempotency key for the lifetime of this form — prevents double-submit
  const [idempotencyKey] = useState(() => crypto.randomUUID());

  // Multi-stop state
  const [stops, setStops] = useState<TaskStop[]>([]);
  const [showPicker, setShowPicker] = useState(false);
  const [savedAddresses, setSavedAddresses] = useState<UserAddress[]>([]);
  const [addressesLoaded, setAddressesLoaded] = useState(false);
  // Location metadata from first stop (populated via Nominatim)
  const [firstStopCity, setFirstStopCity] = useState('');
  const [firstStopCountry, setFirstStopCountry] = useState('');

  // Scheduling state (step 4)
  const [anySchedule, setAnySchedule] = useState(false);
  const [scheduleDate, setScheduleDate] = useState('');
  const [scheduleTime, setScheduleTime] = useState('');

  const currency = apiClient.getCurrency() ?? 'USD';

  // Load saved addresses when reaching step 3
  useEffect(() => {
    if (step === 3 && !addressesLoaded) {
      setAddressesLoaded(true);
      apiClient
        .get<UserAddress[]>('/addresses')
        .then(setSavedAddresses)
        .catch(() => {});
    }
  }, [step, addressesLoaded]);

  const addStop = (stop: TaskStop, city?: string, country?: string) => {
    if (stops.length === 0) {
      setFirstStopCity(city ?? '');
      setFirstStopCountry(country ?? '');
    }
    setStops(prev => [...prev, stop]);
    setShowPicker(false);
  };

  const removeStop = (index: number) => {
    setStops(prev => prev.filter((_, i) => i !== index));
  };

  const descriptionError =
    description.length > 0 && description.length < 10
      ? 'Décrivez votre tâche en au moins 10 caractères'
      : null;

  const budgetNum = parseFloat(budget);
  const budgetError =
    budget.length > 0 && (isNaN(budgetNum) || budgetNum < 1)
      ? 'Entrez un montant valide (minimum 1)'
      : null;

  const canProceed = () => {
    if (step === 1) return description.length >= 10;
    if (step === 2) return budget.length > 0 && !isNaN(budgetNum) && budgetNum >= 1;
    if (step === 3) return stops.length >= 1;
    if (step === 4) return anySchedule || scheduleDate.length > 0;
    return false;
  };

  const buildScheduledAt = (): string | null => {
    if (anySchedule || !scheduleDate) return null;
    const time = scheduleTime || '08:00';
    return new Date(`${scheduleDate}T${time}`).toISOString();
  };

  const handleNext = async () => {
    if (step < 4) {
      setStep(step + 1);
      return;
    }

    if (stops.length === 0) {
      setSubmitError('Ajoutez au moins un lieu d\'exécution.');
      return;
    }

    setSubmitError(null);
    try {
      const task = await createTask({
        description,
        budget,
        mode: taskMode,
        latitude: stops[0].latitude,
        longitude: stops[0].longitude,
        address: stops[0].address,
        stops,
        currency,
        scheduledAt: buildScheduledAt(),
        anySchedule,
        idempotencyKey,
        city: firstStopCity || undefined,
        country: firstStopCountry || undefined,
      });

      if (!task?.id) throw new Error('Création de tâche échouée — aucun ID retourné');

      try {
        await paymentService.createIntent(task.id);
      } catch {
        // Escrow created on next eligible operation
      }

      onSubmit(task.id);
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : 'Échec de la création. Veuillez réessayer.'
      );
    }
  };

  const stepLabels = ['Description', 'Budget', 'Lieux', 'Planification'];

  return (
    <div className="h-full flex flex-col bg-white">
      {showPicker && (
        <StopPicker
          savedAddresses={savedAddresses}
          onConfirm={addStop}
          onClose={() => setShowPicker(false)}
        />
      )}

      {/* Header */}
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={onBack}
            className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-gray-900">Publier une tâche</h2>
            <p className="text-sm text-gray-500">
              Étape {step} / 4 — {stepLabels[step - 1]}
            </p>
          </div>
        </div>

        <div className="flex gap-1.5">
          {[1, 2, 3, 4].map((s) => (
            <div
              key={s}
              className={`h-1.5 flex-1 rounded-full transition-all ${
                s <= step ? 'bg-[#6D28D9]' : 'bg-gray-200'
              }`}
            />
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6">
        {/* ── Step 1: Description ── */}
        {step === 1 && (
          <div>
            <h3 className="text-xl font-bold text-gray-900 mb-1">Décrivez votre tâche</h3>
            <p className="text-sm text-gray-500 mb-6">De quoi avez-vous besoin ?</p>
            <Input
              placeholder="Ex : Nettoyer mon appartement, faire des courses, monter des meubles…"
              value={description}
              onChange={(v) => { setDescription(v); setSubmitError(null); }}
              multiline
              rows={6}
            />
            {descriptionError && (
              <p className="text-xs text-red-500 mt-2 flex items-center gap-1">
                <AlertCircle size={13} /> {descriptionError}
              </p>
            )}
            <p className="text-xs text-gray-400 mt-2 text-right">
              {description.length} car.{description.length < 10 ? ` (encore ${10 - description.length})` : ''}
            </p>
          </div>
        )}

        {/* ── Step 2: Budget ── */}
        {step === 2 && (
          <div>
            <h3 className="text-xl font-bold text-gray-900 mb-1">Fixez votre budget</h3>
            <p className="text-sm text-gray-500 mb-6">Combien êtes-vous prêt à payer ?</p>
            <div className="relative mb-3">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-base text-gray-500 font-semibold">
                {currency}
              </span>
              <input
                type="number"
                min="1"
                placeholder="0"
                value={budget}
                onChange={(e) => { setBudget(e.target.value); setSubmitError(null); }}
                className="w-full pl-16 pr-4 py-4 text-xl font-semibold rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none transition-colors bg-white"
              />
            </div>
            {budgetError && (
              <p className="text-xs text-red-500 mb-3 flex items-center gap-1">
                <AlertCircle size={13} /> {budgetError}
              </p>
            )}
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-3 mb-3">
              <p className="text-sm text-blue-900">
                <span className="font-semibold">Fourchette habituelle :</span>{' '}
                {currency === 'XOF' || currency === 'XAF'
                  ? '5 000 – 25 000 ' + currency
                  : '25 – 75 ' + currency}
              </p>
            </div>
            {taskMode === 'choose' && (
              <p className="text-xs text-gray-500">
                Les prestataires peuvent postuler à ce budget ou proposer un autre prix
              </p>
            )}
          </div>
        )}

        {/* ── Step 3: Lieux d'exécution (multi-stop) ── */}
        {step === 3 && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-xl font-bold text-gray-900">Lieux d'exécution</h3>
              <span className={`text-sm font-semibold ${stops.length >= 4 ? 'text-amber-600' : 'text-gray-400'}`}>
                {stops.length} / 4
              </span>
            </div>
            <p className="text-sm text-gray-500 mb-5">
              Ajoutez jusqu'à 4 points d'arrêt. Le premier sera le point de départ.
            </p>

            {/* Stops list */}
            {stops.length > 0 && (
              <div className="space-y-2 mb-4">
                {stops.map((stop, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-3 bg-white border-2 border-gray-100 rounded-2xl p-3"
                  >
                    <div className="flex flex-col items-center gap-0.5 shrink-0">
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white ${
                        idx === 0 ? 'bg-[#6D28D9]' : 'bg-gray-400'
                      }`}>
                        {idx + 1}
                      </div>
                      {idx < stops.length - 1 && (
                        <div className="w-0.5 h-3 bg-gray-200" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-gray-900 truncate">{stop.address}</p>
                      <p className="text-xs text-gray-400">
                        {idx === 0 ? 'Point de départ' : `Arrêt ${idx}`}
                      </p>
                    </div>
                    <button
                      onClick={() => removeStop(idx)}
                      className="w-7 h-7 rounded-full bg-red-50 flex items-center justify-center text-red-400 hover:bg-red-100 transition-colors shrink-0"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Add stop button */}
            {stops.length < 4 && (
              <button
                onClick={() => setShowPicker(true)}
                className="w-full flex items-center justify-center gap-2 py-3.5 rounded-2xl border-2 border-dashed border-[#6D28D9]/30 hover:border-[#6D28D9] hover:bg-purple-50 transition-all text-[#6D28D9] font-semibold text-sm"
              >
                <Plus size={18} />
                {stops.length === 0 ? 'Ajouter le lieu de départ' : 'Ajouter un arrêt'}
              </button>
            )}

            {stops.length === 0 && (
              <div className="mt-4 bg-amber-50 border border-amber-100 rounded-xl p-3">
                <p className="text-xs text-amber-700">
                  Au moins un lieu est requis pour publier une tâche.
                </p>
              </div>
            )}

            {submitError && (
              <div className="mt-4 flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
                <AlertCircle size={15} className="text-red-500 shrink-0" />
                <p className="text-sm text-red-600">{submitError}</p>
              </div>
            )}
          </div>
        )}

        {/* ── Step 4: Planification ── */}
        {step === 4 && (
          <div>
            <h3 className="text-xl font-bold text-gray-900 mb-1">Quand ?</h3>
            <p className="text-sm text-gray-500 mb-6">Choisissez une date et une heure, ou laissez le prestataire s'organiser.</p>

            {/* Toggle "N'importe quand" */}
            <button
              onClick={() => { setAnySchedule(true); setScheduleDate(''); setScheduleTime(''); }}
              className={`w-full flex items-center gap-4 p-4 rounded-2xl border-2 transition-all mb-3 ${
                anySchedule ? 'border-[#6D28D9] bg-purple-50' : 'border-gray-200 hover:border-[#6D28D9]/40'
              }`}
            >
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${
                anySchedule ? 'bg-[#6D28D9]' : 'bg-gray-100'
              }`}>
                <Infinity size={20} className={anySchedule ? 'text-white' : 'text-gray-500'} />
              </div>
              <div className="text-left">
                <p className={`font-semibold text-sm ${anySchedule ? 'text-[#6D28D9]' : 'text-gray-800'}`}>
                  N'importe quand
                </p>
                <p className="text-xs text-gray-400">Le prestataire propose une disponibilité</p>
              </div>
              {anySchedule && <div className="ml-auto w-5 h-5 rounded-full bg-[#6D28D9] flex items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-white" />
              </div>}
            </button>

            {/* Date/time picker */}
            <button
              onClick={() => setAnySchedule(false)}
              className={`w-full flex items-center gap-4 p-4 rounded-2xl border-2 transition-all mb-4 ${
                !anySchedule ? 'border-[#6D28D9] bg-purple-50' : 'border-gray-200 hover:border-[#6D28D9]/40'
              }`}
            >
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${
                !anySchedule ? 'bg-[#6D28D9]' : 'bg-gray-100'
              }`}>
                <Calendar size={20} className={!anySchedule ? 'text-white' : 'text-gray-500'} />
              </div>
              <div className="text-left">
                <p className={`font-semibold text-sm ${!anySchedule ? 'text-[#6D28D9]' : 'text-gray-800'}`}>
                  Date précise
                </p>
                <p className="text-xs text-gray-400">Choisir une date et heure</p>
              </div>
              {!anySchedule && <div className="ml-auto w-5 h-5 rounded-full bg-[#6D28D9] flex items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-white" />
              </div>}
            </button>

            {!anySchedule && (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                    Date
                  </label>
                  <div className="relative">
                    <Calendar size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                    <input
                      type="date"
                      value={scheduleDate}
                      min={new Date().toISOString().split('T')[0]}
                      onChange={(e) => setScheduleDate(e.target.value)}
                      className="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-gray-900 bg-white"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                    Heure <span className="font-normal normal-case text-gray-400">(optionnelle)</span>
                  </label>
                  <div className="relative">
                    <Clock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                    <input
                      type="time"
                      value={scheduleTime}
                      onChange={(e) => setScheduleTime(e.target.value)}
                      className="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-gray-900 bg-white"
                    />
                  </div>
                  {!scheduleTime && (
                    <p className="text-xs text-gray-400 mt-1">Si non renseignée, l'heure sera flexible.</p>
                  )}
                </div>
              </div>
            )}

            {submitError && (
              <div className="mt-4 flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
                <AlertCircle size={15} className="text-red-500 shrink-0" />
                <p className="text-sm text-red-600">{submitError}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom CTA */}
      <div className="px-6 pb-8 pt-4 bg-white border-t border-gray-100">
        <Button
          variant="primary"
          fullWidth
          disabled={!canProceed() || loading}
          onClick={handleNext}
        >
          {loading
            ? 'Création en cours…'
            : step < 4
            ? 'Continuer'
            : 'Publier la tâche'}
        </Button>
      </div>
    </div>
  );
}
