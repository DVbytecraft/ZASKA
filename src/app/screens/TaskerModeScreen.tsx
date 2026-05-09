import { useEffect, useState, useCallback } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { MapPin, Clock, RefreshCw, AlertCircle, Loader2, ChevronDown, ChevronUp, Navigation, Search, Globe, X } from 'lucide-react';
import { taskService, apiClient } from '@zaska/shared-services';
import type { Task, UserAddress } from '@zaska/shared-services';
import { requestGeolocation } from '../hooks/useTaskFlow';

interface TaskerModeScreenProps {
  onApply: (taskId: string) => void;
  onBack?: () => void;
}

// ── Distance badge ────────────────────────────────────────────────────────────
function DistanceBadge({ km }: { km: number | null | undefined }) {
  if (km === null || km === undefined) {
    return <span className="text-xs text-gray-400 italic">Distance inconnue</span>;
  }
  if (km < 20) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
        {km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1)} km`} · Candidat idéal
      </span>
    );
  }
  if (km < 100) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
        À {km.toFixed(0)} km
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">
      <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
      Loin de vous · {km.toFixed(0)} km
    </span>
  );
}

// ── Task card ─────────────────────────────────────────────────────────────────
function TaskCard({ task, onApply }: { task: Task; onApply: (id: string) => void }) {
  // Execution location: prefer structured city/country over raw address
  const execLocation = task.city
    ? [task.city, task.country].filter(Boolean).join(', ')
    : task.address ?? null;

  return (
    <Card className="hover:shadow-lg transition-all">
      <div className="flex items-start justify-between mb-2">
        <h3 className="text-base font-semibold text-gray-900 flex-1 pr-2 leading-snug">
          {task.title || task.description?.slice(0, 60)}
        </h3>
        <span className="text-base font-bold text-[#1E40AF] whitespace-nowrap">
          {Number(task.price).toLocaleString()} <span className="text-xs font-semibold text-gray-400">{task.currency}</span>
        </span>
      </div>

      {/* Execution location — prominently displayed */}
      {execLocation && (
        <div className="flex items-center gap-1.5 mb-2">
          <MapPin size={13} className="text-[#6D28D9] shrink-0" />
          <span className="text-sm font-medium text-gray-700">{execLocation}</span>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <DistanceBadge km={task.distanceKm} />
        {task.mode === 'choose' && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-medium">Candidature</span>
        )}
        {task.scheduledAt && (
          <span className="inline-flex items-center gap-1 text-xs text-purple-600 bg-purple-50 rounded-full px-2 py-0.5">
            <Clock size={11} /> {new Date(task.scheduledAt).toLocaleDateString('fr-FR')}
          </span>
        )}
        {task.anySchedule && (
          <span className="text-xs text-gray-400 italic">Date flexible</span>
        )}
      </div>

      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-400">
          {task.createdAt ? new Date(task.createdAt).toLocaleDateString('fr-FR') : ''}
          {task.negotiationStatus && task.negotiationStatus !== 'none' ? ' · Prix négociable' : ''}
        </p>
        <Button size="md" onClick={() => onApply(task.id)}>Postuler</Button>
      </div>
    </Card>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────
export function TaskerModeScreen({ onApply }: TaskerModeScreenProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFar, setShowFar] = useState(false);

  // Reference position — used to compute distance from ME to the task's execution location
  const [refLabel, setRefLabel] = useState<string>('Chargement...');
  const [refCoords, setRefCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [savedAddresses, setSavedAddresses] = useState<UserAddress[]>([]);
  const [showAddressPicker, setShowAddressPicker] = useState(false);

  // Execution-location filters — search by WHERE the task will be performed (independent of user position)
  const [filterCity, setFilterCity] = useState('');
  const [filterCountry, setFilterCountry] = useState('');
  const [debouncedCity, setDebouncedCity] = useState('');
  const [debouncedCountry, setDebouncedCountry] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  // Debounce filter inputs: update debounced values 600ms after typing stops
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedCity(filterCity);
      setDebouncedCountry(filterCountry);
    }, 600);
    return () => clearTimeout(t);
  }, [filterCity, filterCountry]);

  const myId = apiClient.getUserId();

  // Load saved addresses
  useEffect(() => {
    apiClient.get<UserAddress[]>('/addresses').then(setSavedAddresses).catch(() => {});
  }, []);

  // Get GPS on mount
  useEffect(() => {
    requestGeolocation()
      .then(({ latitude, longitude }) => {
        setRefCoords({ lat: latitude, lng: longitude });
        setRefLabel('Ma position GPS');
      })
      .catch(() => {
        // Try default address from saved list
        const def = savedAddresses.find(a => a.isDefault);
        if (def?.latitude && def?.longitude) {
          setRefCoords({ lat: def.latitude, lng: def.longitude });
          setRefLabel(`${def.label} · ${def.city}`);
        } else {
          setRefLabel('Position indisponible');
        }
      });
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    taskService
      .browseAvailableTasks(
        refCoords?.lat,
        refCoords?.lng,
        debouncedCountry.trim() || undefined,
        debouncedCity.trim() || undefined,
      )
      .then((data) => setTasks(data.filter(t => t.createdBy !== myId)))
      .catch((err) => setError(err instanceof Error ? err.message : 'Erreur'))
      .finally(() => setLoading(false));
  }, [refCoords, myId, debouncedCountry, debouncedCity]);

  useEffect(() => { load(); }, [load]);

  const nearTasks = tasks.filter(t => (t.distanceKm ?? Infinity) < 100);
  const farTasks = tasks.filter(t => (t.distanceKm ?? Infinity) >= 100);

  const selectAddress = (addr: UserAddress) => {
    if (addr.latitude && addr.longitude) {
      setRefCoords({ lat: addr.latitude, lng: addr.longitude });
      setRefLabel(`${addr.label} · ${addr.city}`);
    }
    setShowAddressPicker(false);
  };

  const selectGps = () => {
    requestGeolocation()
      .then(({ latitude, longitude }) => {
        setRefCoords({ lat: latitude, lng: longitude });
        setRefLabel('Ma position GPS');
      })
      .catch(() => {})
      .finally(() => setShowAddressPicker(false));
  };

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      {/* Header */}
      <div className="px-6 pt-8 pb-5 bg-gradient-to-br from-[#1E40AF] to-[#1E3A8A]">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Tâches disponibles</h1>
            <p className="text-white/70 text-sm">Postule et commence à gagner</p>
          </div>
          <button onClick={load} className="w-10 h-10 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center border border-white/10">
            <RefreshCw size={16} className="text-white" />
          </button>
        </div>

        {/* Reference location switcher */}
        <button
          onClick={() => setShowAddressPicker(!showAddressPicker)}
          className="w-full flex items-center gap-2 px-4 py-2.5 bg-white/15 hover:bg-white/25 rounded-xl border border-white/20 transition-all"
        >
          <Navigation size={14} className="text-white/80 flex-shrink-0" />
          <span className="flex-1 text-left text-sm font-medium text-white truncate">{refLabel}</span>
          <ChevronDown size={14} className="text-white/60" />
        </button>

        {/* Address picker dropdown */}
        {showAddressPicker && (
          <div className="mt-2 bg-white rounded-xl shadow-xl overflow-hidden">
            <button onClick={selectGps} className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 border-b border-gray-100">
              <Navigation size={16} className="text-blue-600" />
              <span className="text-sm font-medium text-gray-900">Ma position actuelle (GPS)</span>
            </button>
            {savedAddresses.map(addr => (
              <button
                key={addr.id}
                onClick={() => selectAddress(addr)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 border-b border-gray-100 last:border-0"
              >
                <MapPin size={16} className={addr.isDefault ? 'text-purple-600' : 'text-gray-400'} />
                <div className="flex-1 text-left">
                  <p className="text-sm font-medium text-gray-900">{addr.label}</p>
                  <p className="text-xs text-gray-400">{addr.city}, {addr.country}</p>
                </div>
                {addr.isDefault && <span className="text-xs text-purple-600 font-semibold">Par défaut</span>}
              </button>
            ))}
          </div>
        )}

        {/* Execution-location filter — independent of user position */}
        <div className="mt-3">
          <button
            onClick={() => setShowFilters(v => !v)}
            className="flex items-center gap-2 text-xs font-semibold text-white/80 hover:text-white"
          >
            <Globe size={13} />
            {(filterCity || filterCountry)
              ? `Lieu d'exécution : ${[filterCity, filterCountry].filter(Boolean).join(', ')}`
              : "Filtrer par lieu d'exécution"}
            {(filterCity || filterCountry) && (
              <span
                onClick={e => { e.stopPropagation(); setFilterCity(''); setFilterCountry(''); }}
                className="ml-1 bg-white/20 hover:bg-white/40 rounded-full px-1.5 py-0.5 text-white text-xs"
              >✕</span>
            )}
          </button>

          {showFilters && (
            <div className="mt-2 bg-white rounded-xl p-3 space-y-2 shadow-lg">
              <p className="text-xs text-gray-400 font-medium">Filtrer les tâches par lieu d'exécution (indépendant de votre position)</p>
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Ville (ex : Lomé, Abidjan, Paris…)"
                  value={filterCity}
                  onChange={e => setFilterCity(e.target.value)}
                  className="w-full pl-8 pr-3 py-2 text-sm rounded-lg border border-gray-200 focus:border-[#6D28D9] focus:outline-none text-gray-900"
                />
              </div>
              <div className="relative">
                <Globe size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Pays (ex : Togo, Côte d'Ivoire, France…)"
                  value={filterCountry}
                  onChange={e => setFilterCountry(e.target.value)}
                  className="w-full pl-8 pr-3 py-2 text-sm rounded-lg border border-gray-200 focus:border-[#6D28D9] focus:outline-none text-gray-900"
                />
              </div>
              {(filterCity || filterCountry) && (
                <button
                  onClick={() => { setFilterCity(''); setFilterCountry(''); setShowFilters(false); }}
                  className="w-full text-xs text-red-500 hover:text-red-700 font-medium py-1"
                >
                  Effacer les filtres
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="px-6 py-4 space-y-3">
        {loading && (
          <div className="flex items-center justify-center h-48">
            <Loader2 size={32} className="animate-spin text-blue-600" />
          </div>
        )}

        {error && !loading && (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <AlertCircle size={36} className="text-red-400" />
            <p className="text-sm text-red-600 text-center">{error}</p>
            <button onClick={load} className="text-sm font-semibold text-blue-700 hover:underline">Réessayer</button>
          </div>
        )}

        {/* Active filter banner */}
        {(filterCity || filterCountry) && !loading && (
          <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 rounded-xl border border-blue-100">
            <Globe size={14} className="text-blue-600 shrink-0" />
            <span className="text-xs text-blue-800 font-medium flex-1">
              Lieu d'exécution : <strong>{[filterCity, filterCountry].filter(Boolean).join(', ')}</strong>
            </span>
            <button onClick={() => { setFilterCity(''); setFilterCountry(''); }} className="text-blue-400 hover:text-blue-700">
              <X size={14} />
            </button>
          </div>
        )}

        {!loading && !error && tasks.length === 0 && (
          <div className="flex flex-col items-center justify-center h-48 gap-3 text-gray-400">
            <Clock size={40} className="text-gray-300" />
            <p className="text-sm font-medium text-center">
              {(filterCity || filterCountry)
                ? `Aucune tâche trouvée à ${[filterCity, filterCountry].filter(Boolean).join(', ')}`
                : 'Aucune tâche disponible pour le moment'}
            </p>
            {(filterCity || filterCountry) && (
              <button onClick={() => { setFilterCity(''); setFilterCountry(''); }} className="text-xs text-[#6D28D9] font-semibold underline">
                Voir toutes les tâches
              </button>
            )}
          </div>
        )}

        {/* Section 1 — Near tasks */}
        {!loading && !error && nearTasks.length > 0 && (
          <>
            <div className="flex items-center gap-2 pt-2">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                Près de vous ({nearTasks.length})
              </p>
            </div>
            {nearTasks.map(task => (
              <TaskCard key={task.id} task={task} onApply={onApply} />
            ))}
          </>
        )}

        {/* Section 2 — Far tasks, collapsible */}
        {!loading && !error && farTasks.length > 0 && (
          <>
            <button
              onClick={() => setShowFar(v => !v)}
              className="w-full flex items-center justify-between px-4 py-3 bg-gray-100 hover:bg-gray-200 rounded-xl transition-colors mt-2"
            >
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-400" />
                <span className="text-sm font-semibold text-gray-600">
                  Autres régions · {farTasks.length} tâche{farTasks.length > 1 ? 's' : ''}
                </span>
              </div>
              {showFar ? <ChevronUp size={16} className="text-gray-500" /> : <ChevronDown size={16} className="text-gray-500" />}
            </button>

            {showFar && farTasks.map(task => (
              <TaskCard key={task.id} task={task} onApply={onApply} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
