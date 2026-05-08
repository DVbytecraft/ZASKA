import { useEffect, useState } from 'react';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { ArrowLeft, MapPin, Loader, AlertCircle, Navigation, Search, CheckCircle2 } from 'lucide-react';
import { useTaskFlow, requestGeolocation } from '../hooks/useTaskFlow';
import { paymentService, apiClient } from '@zaska/shared-services';
import type { TaskMode, UserAddress } from '@zaska/shared-services';

interface PostTaskScreenProps {
  taskMode: TaskMode;
  onBack: () => void;
  onSubmit: (taskId: string) => void;
}

interface Coords {
  latitude: number;
  longitude: number;
}

type LocSource = 'gps' | 'saved' | 'manual';

async function geocodeCity(city: string): Promise<{ lat: number; lng: number } | null> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(city)}&format=json&limit=1`,
      { headers: { 'Accept-Language': 'fr,en' } }
    );
    const data = await res.json();
    if (Array.isArray(data) && data.length > 0) {
      return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };
    }
  } catch {
    // ignore network errors
  }
  return null;
}

export function PostTaskScreen({ taskMode, onBack, onSubmit }: PostTaskScreenProps) {
  const [step, setStep] = useState(1);
  const [description, setDescription] = useState('');
  const [budget, setBudget] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { createTask, loading } = useTaskFlow();

  // Location state
  const [coords, setCoords] = useState<Coords | null>(null);
  const [addressLabel, setAddressLabel] = useState('');
  const [locSource, setLocSource] = useState<LocSource | null>(null);

  // GPS sub-state
  const [gpsLoading, setGpsLoading] = useState(false);
  const [gpsError, setGpsError] = useState<string | null>(null);

  // Saved addresses
  const [savedAddresses, setSavedAddresses] = useState<UserAddress[]>([]);
  const [addressesLoading, setAddressesLoading] = useState(false);

  // Manual city entry
  const [manualCity, setManualCity] = useState('');
  const [geocoding, setGeocoding] = useState(false);
  const [geocodeError, setGeocodeError] = useState<string | null>(null);

  const currency = apiClient.getCurrency() ?? 'USD';

  // Load saved addresses when reaching step 3
  useEffect(() => {
    if (step === 3 && savedAddresses.length === 0) {
      setAddressesLoading(true);
      apiClient
        .get<UserAddress[]>('/addresses')
        .then(setSavedAddresses)
        .catch(() => {})
        .finally(() => setAddressesLoading(false));
    }
  }, [step]);

  const selectGps = () => {
    setLocSource('gps');
    setGpsLoading(true);
    setGpsError(null);
    requestGeolocation()
      .then(({ latitude, longitude }) => {
        setCoords({ latitude, longitude });
        setAddressLabel('Ma position actuelle (GPS)');
      })
      .catch(() => {
        setGpsError('Accès à la position refusé. Activez la géolocalisation.');
        setCoords(null);
        setAddressLabel('');
      })
      .finally(() => setGpsLoading(false));
  };

  const selectSavedAddress = (addr: UserAddress) => {
    if (!addr.latitude || !addr.longitude) return;
    setLocSource('saved');
    setCoords({ latitude: addr.latitude, longitude: addr.longitude });
    setAddressLabel(`${addr.label} · ${addr.city}`);
    setGpsError(null);
    setGeocodeError(null);
  };

  const handleGeocode = async () => {
    if (!manualCity.trim()) return;
    setGeocoding(true);
    setGeocodeError(null);
    const result = await geocodeCity(manualCity.trim());
    setGeocoding(false);
    if (result) {
      setLocSource('manual');
      setCoords({ latitude: result.lat, longitude: result.lng });
      setAddressLabel(manualCity.trim());
      setGpsError(null);
    } else {
      setGeocodeError(`Ville introuvable : "${manualCity}". Essayez un nom plus précis.`);
      setCoords(null);
      setAddressLabel('');
    }
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
    if (step === 3) return coords !== null && addressLabel !== '';
    return false;
  };

  const handleNext = async () => {
    if (step < 3) {
      setStep(step + 1);
      return;
    }

    if (!coords) {
      setSubmitError('Le lieu d\'exécution est obligatoire.');
      return;
    }

    setSubmitError(null);
    try {
      const task = await createTask({
        description,
        budget,
        mode: taskMode,
        latitude: coords.latitude,
        longitude: coords.longitude,
        address: addressLabel,
        currency,
      });

      if (!task?.id) throw new Error('Création de tâche échouée — aucun ID retourné');

      try {
        await paymentService.createIntent(task.id);
      } catch {
        // Escrow will be created on next eligible operation
      }

      onSubmit(task.id);
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : 'Échec de la création. Veuillez réessayer.'
      );
    }
  };

  const stepLabels = ['Description', 'Budget', 'Lieu d\'exécution'];

  return (
    <div className="h-full flex flex-col bg-white">
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
              Étape {step} / 3 — {stepLabels[step - 1]}
            </p>
          </div>
        </div>

        <div className="flex gap-1.5">
          {[1, 2, 3].map((s) => (
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
        {/* ── Step 1 ── */}
        {step === 1 && (
          <div>
            <h3 className="text-xl font-bold text-gray-900 mb-1">Décrivez votre tâche</h3>
            <p className="text-sm text-gray-500 mb-6">De quoi avez-vous besoin ?</p>
            <Input
              placeholder="Ex : Nettoyer mon appartement, faire des courses, monter des meubles…"
              value={description}
              onChange={(v) => {
                setDescription(v);
                setSubmitError(null);
              }}
              multiline
              rows={6}
            />
            {descriptionError && (
              <p className="text-xs text-red-500 mt-2 flex items-center gap-1">
                <AlertCircle size={13} /> {descriptionError}
              </p>
            )}
            <p className="text-xs text-gray-400 mt-2 text-right">
              {description.length} car.
              {description.length < 10 ? ` (encore ${10 - description.length})` : ''}
            </p>
          </div>
        )}

        {/* ── Step 2 ── */}
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
                onChange={(e) => {
                  setBudget(e.target.value);
                  setSubmitError(null);
                }}
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

        {/* ── Step 3 — Execution location picker ── */}
        {step === 3 && (
          <div>
            <h3 className="text-xl font-bold text-gray-900 mb-1">
              Où la tâche doit-elle être exécutée ?
            </h3>
            <p className="text-sm text-gray-500 mb-5">
              Choisissez le lieu d'exécution. Les prestataires proches verront cette tâche en
              priorité.
            </p>

            {/* Selected location confirmation */}
            {coords && addressLabel && (
              <div className="mb-4 flex items-center gap-3 px-4 py-3 bg-green-50 border border-green-200 rounded-xl">
                <CheckCircle2 size={20} className="text-green-600 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-green-800 truncate">{addressLabel}</p>
                  <p className="text-xs text-green-600">
                    {coords.latitude.toFixed(4)}, {coords.longitude.toFixed(4)}
                  </p>
                </div>
              </div>
            )}

            {/* Option 1: GPS */}
            <button
              onClick={selectGps}
              disabled={gpsLoading}
              className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-xl border-2 mb-2 text-left transition-all ${
                locSource === 'gps' && coords
                  ? 'border-[#6D28D9] bg-purple-50'
                  : 'border-gray-200 hover:border-gray-300 bg-white'
              }`}
            >
              {gpsLoading ? (
                <Loader size={20} className="text-[#6D28D9] animate-spin flex-shrink-0" />
              ) : (
                <Navigation
                  size={20}
                  className={`flex-shrink-0 ${
                    locSource === 'gps' && coords ? 'text-[#6D28D9]' : 'text-gray-400'
                  }`}
                />
              )}
              <div>
                <p className="text-sm font-semibold text-gray-900">Ma position actuelle (GPS)</p>
                <p className="text-xs text-gray-400">Utilise votre localisation en temps réel</p>
              </div>
            </button>
            {gpsError && locSource === 'gps' && (
              <p className="text-xs text-red-500 mb-2 ml-1 flex items-center gap-1">
                <AlertCircle size={12} /> {gpsError}
              </p>
            )}

            {/* Option 2: Saved addresses */}
            {addressesLoading ? (
              <div className="flex items-center gap-2 py-2 px-1 mb-2">
                <Loader size={14} className="animate-spin text-gray-400" />
                <span className="text-xs text-gray-400">Chargement des adresses…</span>
              </div>
            ) : (
              savedAddresses.map((addr) => (
                <button
                  key={addr.id}
                  onClick={() => selectSavedAddress(addr)}
                  disabled={!addr.latitude || !addr.longitude}
                  className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-xl border-2 mb-2 text-left transition-all ${
                    locSource === 'saved' && addressLabel === `${addr.label} · ${addr.city}`
                      ? 'border-[#6D28D9] bg-purple-50'
                      : 'border-gray-200 hover:border-gray-300 bg-white'
                  } ${!addr.latitude || !addr.longitude ? 'opacity-40 cursor-not-allowed' : ''}`}
                >
                  <MapPin
                    size={20}
                    className={`flex-shrink-0 ${
                      locSource === 'saved' && addressLabel === `${addr.label} · ${addr.city}`
                        ? 'text-[#6D28D9]'
                        : addr.isDefault
                        ? 'text-purple-400'
                        : 'text-gray-400'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-gray-900 truncate">{addr.label}</p>
                      {addr.isDefault && (
                        <span className="text-[10px] font-bold text-purple-600 bg-purple-100 px-1.5 py-0.5 rounded-full">
                          Défaut
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 truncate">
                      {addr.city}, {addr.country}
                    </p>
                  </div>
                </button>
              ))
            )}

            {/* Option 3: Manual city */}
            <div
              className={`rounded-xl border-2 mb-2 overflow-hidden transition-all ${
                locSource === 'manual' && coords
                  ? 'border-[#6D28D9] bg-purple-50'
                  : 'border-gray-200 bg-white'
              }`}
            >
              <div className="flex items-center gap-3 px-4 pt-3.5 pb-2">
                <Search
                  size={20}
                  className={`flex-shrink-0 ${
                    locSource === 'manual' && coords ? 'text-[#6D28D9]' : 'text-gray-400'
                  }`}
                />
                <p className="text-sm font-semibold text-gray-900">Saisir une ville</p>
              </div>
              <div className="px-4 pb-3.5 flex gap-2">
                <input
                  type="text"
                  placeholder="Ex : Cotonou, Paris, Abidjan…"
                  value={manualCity}
                  onChange={(e) => {
                    setManualCity(e.target.value);
                    setGeocodeError(null);
                    if (locSource === 'manual') {
                      setCoords(null);
                      setAddressLabel('');
                    }
                  }}
                  onKeyDown={(e) => e.key === 'Enter' && handleGeocode()}
                  className="flex-1 px-3 py-2 text-sm rounded-lg border border-gray-200 focus:border-[#6D28D9] focus:outline-none bg-white"
                />
                <button
                  onClick={handleGeocode}
                  disabled={!manualCity.trim() || geocoding}
                  className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#6D28D9] text-white disabled:opacity-40 flex items-center gap-1.5"
                >
                  {geocoding ? (
                    <Loader size={14} className="animate-spin" />
                  ) : (
                    'OK'
                  )}
                </button>
              </div>
              {geocodeError && (
                <p className="text-xs text-red-500 px-4 pb-3 flex items-center gap-1">
                  <AlertCircle size={12} /> {geocodeError}
                </p>
              )}
            </div>

            <p className="text-xs text-gray-400 mt-3 text-center">
              Le lieu choisi détermine quels prestataires reçoivent la tâche en priorité
            </p>
          </div>
        )}

        {submitError && (
          <div className="mt-4 bg-red-50 border border-red-100 rounded-xl p-3 flex items-start gap-2">
            <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-600">{submitError}</p>
          </div>
        )}
      </div>

      <div className="px-6 py-4 border-t border-gray-200">
        <Button
          fullWidth
          onClick={handleNext}
          disabled={!canProceed() || loading || geocoding || gpsLoading}
        >
          {loading
            ? 'Publication en cours…'
            : step === 3
            ? 'Publier la tâche'
            : 'Suivant'}
        </Button>
      </div>
    </div>
  );
}
