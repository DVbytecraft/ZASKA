import { useEffect, useMemo, useState } from 'react';
import {
  adminApi,
  type AdminCountry,
  type AdminGeoContinent,
  type AdminGeoCountryRuntime,
  type AdminModuleRuntimeEntry,
  type AdminPlatformModule,
} from '../adminApi';

function prettyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function getCountryCode(country: AdminGeoCountryRuntime | null | undefined) {
  return country?.country_code ?? country?.countryCode ?? country?.code ?? '';
}

function getContinentCode(country: AdminGeoCountryRuntime | null | undefined) {
  return country?.continent_code ?? country?.continentCode ?? '';
}

function getPricingProfile(country: AdminGeoCountryRuntime | null | undefined) {
  return country?.pricing_profile ?? country?.pricingProfile ?? {};
}

export function CountriesPage() {
  const [countries, setCountries] = useState<AdminCountry[]>([]);
  const [geoCountries, setGeoCountries] = useState<AdminGeoCountryRuntime[]>([]);
  const [continents, setContinents] = useState<AdminGeoContinent[]>([]);
  const [modules, setModules] = useState<AdminPlatformModule[]>([]);
  const [moduleRuntime, setModuleRuntime] = useState<Record<string, AdminModuleRuntimeEntry>>({});
  const [selectedCountryCode, setSelectedCountryCode] = useState('');
  const [countrySearch, setCountrySearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingCountryCode, setSavingCountryCode] = useState<string | null>(null);
  const [savingModuleCode, setSavingModuleCode] = useState<string | null>(null);
  const [countryPricingDraft, setCountryPricingDraft] = useState('{}');
  const [continentPricingDraft, setContinentPricingDraft] = useState('{}');
  const [countryPricingError, setCountryPricingError] = useState<string | null>(null);
  const [continentPricingError, setContinentPricingError] = useState<string | null>(null);
  const [savingCountryPricing, setSavingCountryPricing] = useState(false);
  const [savingContinentPricing, setSavingContinentPricing] = useState(false);

  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        const [countriesRes, continentsRes, modulesRes, geoCountriesRes] = await Promise.all([
          adminApi.getCountries(),
          adminApi.getGeoContinents(),
          adminApi.getModuleCatalog(),
          adminApi.getGeoCountriesRuntime(),
        ]);
        if (!active) return;
        setCountries(countriesRes);
        setContinents(continentsRes);
        setModules(modulesRes.modules);
        setGeoCountries(geoCountriesRes);
        setSelectedCountryCode((current) => current || countriesRes[0]?.code || geoCountriesRes[0]?.country_code || '');
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : 'Erreur de chargement');
      } finally {
        if (active) setLoading(false);
      }
    };

    void load();

    return () => {
      active = false;
    };
  }, []);

  const selectedCountry = useMemo(
    () => countries.find((country) => country.code === selectedCountryCode) ?? null,
    [countries, selectedCountryCode],
  );

  const selectedGeoCountry = useMemo(
    () => geoCountries.find((country) => getCountryCode(country) === selectedCountryCode) ?? null,
    [geoCountries, selectedCountryCode],
  );

  const selectedContinentCode = getContinentCode(selectedGeoCountry);

  const selectedContinent = useMemo(
    () => continents.find((continent) => continent.code === selectedContinentCode) ?? null,
    [continents, selectedContinentCode],
  );

  useEffect(() => {
    if (!selectedCountryCode) return;
    let active = true;

    const loadRuntime = async () => {
      try {
        const [runtime, geoCountry, countryTemplate] = await Promise.all([
          adminApi.getModuleRuntime(selectedCountryCode),
          adminApi.getGeoCountryRuntime(selectedCountryCode),
          adminApi.getCountryPricingTemplate(selectedCountryCode),
        ]);
        if (!active) return;
        setModuleRuntime(runtime);
        setGeoCountries((items) => {
          const next = items.filter((item) => getCountryCode(item) !== selectedCountryCode);
          return [...next, geoCountry];
        });
        setCountryPricingDraft(prettyJson(getPricingProfile(geoCountry) || countryTemplate.pricing_profile));
        setCountryPricingError(null);

        const continentCode = getContinentCode(geoCountry);
        if (continentCode) {
          const [continentTemplate] = await Promise.all([
            adminApi.getContinentPricingTemplate(continentCode),
          ]);
          if (!active) return;
          const matchingContinent = continents.find((item) => item.code === continentCode);
          setContinentPricingDraft(prettyJson(matchingContinent?.pricing_profile ?? continentTemplate.pricing_profile));
          setContinentPricingError(null);
        } else {
          setContinentPricingDraft('{}');
        }
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : 'Erreur de chargement des réglages pays');
      }
    };

    void loadRuntime();

    return () => {
      active = false;
    };
  }, [selectedCountryCode, continents]);

  const filteredCountries = useMemo(() => {
    const query = countrySearch.trim().toLowerCase();
    if (!query) return countries;
    return countries.filter((country) =>
      [country.code, country.name_fr, country.name_en, country.currency]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query)),
    );
  }, [countries, countrySearch]);

  const modulesByGroup = useMemo(() => {
    const groups = new Map<string, AdminPlatformModule[]>();
    modules.forEach((module) => {
      const key = module.module_group || 'other';
      groups.set(key, [...(groups.get(key) ?? []), module]);
    });
    return Array.from(groups.entries());
  }, [modules]);

  async function toggleCountry(country: AdminCountry, patch: Partial<AdminCountry>) {
    try {
      setSavingCountryCode(country.code);
      const updated = await adminApi.updateCountry(country.code, patch);
      setCountries((items) => items.map((item) => (item.code === country.code ? { ...item, ...updated } : item)));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur de mise à jour');
    } finally {
      setSavingCountryCode(null);
    }
  }

  async function toggleModule(moduleCode: string, enabled: boolean) {
    if (!selectedCountryCode) return;
    try {
      setSavingModuleCode(moduleCode);
      await adminApi.updateModuleSetting(moduleCode, {
        scope_type: 'country',
        scope_value: selectedCountryCode,
        enabled,
        reason: 'frontend-admin-country-console',
      });
      const runtime = await adminApi.getModuleRuntime(selectedCountryCode);
      setModuleRuntime(runtime);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur de mise à jour du module');
    } finally {
      setSavingModuleCode(null);
    }
  }

  async function saveCountryPricing() {
    if (!selectedCountryCode) return;
    try {
      setSavingCountryPricing(true);
      const parsed = JSON.parse(countryPricingDraft) as Record<string, unknown>;
      await adminApi.updateCountryPricing(selectedCountryCode, parsed);
      const refreshed = await adminApi.getGeoCountryRuntime(selectedCountryCode);
      setGeoCountries((items) => {
        const next = items.filter((item) => getCountryCode(item) !== selectedCountryCode);
        return [...next, refreshed];
      });
      setCountryPricingDraft(prettyJson(getPricingProfile(refreshed)));
      setCountryPricingError(null);
      setError(null);
    } catch (e) {
      setCountryPricingError(e instanceof Error ? e.message : 'JSON pricing pays invalide');
    } finally {
      setSavingCountryPricing(false);
    }
  }

  async function saveContinentPricing() {
    if (!selectedContinentCode) return;
    try {
      setSavingContinentPricing(true);
      const parsed = JSON.parse(continentPricingDraft) as Record<string, unknown>;
      await adminApi.updateContinentPricing(selectedContinentCode, parsed);
      const refreshedContinents = await adminApi.getGeoContinents();
      setContinents(refreshedContinents);
      const refreshed = refreshedContinents.find((item) => item.code === selectedContinentCode);
      setContinentPricingDraft(prettyJson(refreshed?.pricing_profile ?? parsed));
      setContinentPricingError(null);
      setError(null);
    } catch (e) {
      setContinentPricingError(e instanceof Error ? e.message : 'JSON pricing continent invalide');
    } finally {
      setSavingContinentPricing(false);
    }
  }

  async function loadCountryTemplate() {
    if (!selectedCountryCode) return;
    try {
      const template = await adminApi.getCountryPricingTemplate(selectedCountryCode);
      setCountryPricingDraft(prettyJson(template.pricing_profile));
      setCountryPricingError(null);
    } catch (e) {
      setCountryPricingError(e instanceof Error ? e.message : 'Impossible de charger le template pays');
    }
  }

  async function loadContinentTemplate() {
    if (!selectedContinentCode) return;
    try {
      const template = await adminApi.getContinentPricingTemplate(selectedContinentCode);
      setContinentPricingDraft(prettyJson(template.pricing_profile));
      setContinentPricingError(null);
    } catch (e) {
      setContinentPricingError(e instanceof Error ? e.message : 'Impossible de charger le template continent');
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="mb-2 text-2xl font-bold text-gray-900">Pays, modules & tarifs</h2>
        <p className="text-sm text-gray-600">
          Pilotez l’ouverture des pays, l’activation des modules et les prix de base VTC/livraison sans toucher au code.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <span className="text-sm font-medium text-gray-600">Pays connus</span>
          <p className="mt-2 text-3xl font-bold text-gray-900">{loading ? '—' : countries.length}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <span className="text-sm font-medium text-gray-600">Pays actifs</span>
          <p className="mt-2 text-3xl font-bold text-green-600">{loading ? '—' : countries.filter((item) => item.is_active).length}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <span className="text-sm font-medium text-gray-600">Modules publics</span>
          <p className="mt-2 text-3xl font-bold text-violet-600">{loading ? '—' : modules.filter((item) => item.is_public).length}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <span className="text-sm font-medium text-gray-600">Continents couverts</span>
          <p className="mt-2 text-3xl font-bold text-blue-600">{loading ? '—' : continents.length}</p>
        </div>
      </div>

      {error ? <p className="rounded-xl bg-red-50 p-4 text-sm text-red-600">{error}</p> : null}

      <div className="grid gap-6 xl:grid-cols-[340px,minmax(0,1fr)]">
        <aside className="space-y-4 rounded-2xl border border-gray-200 bg-white p-5">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Répertoire pays</h3>
            <p className="mt-1 text-sm text-gray-500">Choisissez un marché pour gérer son ouverture, ses modules et son pricing.</p>
          </div>
          <input
            type="text"
            value={countrySearch}
            onChange={(event) => setCountrySearch(event.target.value)}
            placeholder="Rechercher un pays"
            className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm"
          />
          <div className="max-h-[780px] space-y-2 overflow-auto pr-1">
            {filteredCountries.map((country) => (
              <button
                key={country.code}
                type="button"
                onClick={() => setSelectedCountryCode(country.code)}
                className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                  selectedCountryCode === country.code ? 'border-black bg-gray-50' : 'border-gray-200 bg-white hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-gray-900">{country.name_fr ?? country.name_en ?? country.code}</p>
                    <p className="mt-1 text-xs text-gray-500">{country.code} · {country.currency}</p>
                  </div>
                  <span
                    className={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                      country.launch_status === 'ACTIVE'
                        ? 'bg-green-100 text-green-700'
                        : country.launch_status === 'CONFIGURED'
                          ? 'bg-blue-100 text-blue-700'
                          : country.launch_status === 'SUSPENDED'
                            ? 'bg-red-100 text-red-700'
                            : 'bg-gray-100 text-gray-500'
                    }`}
                  >
                    {country.launch_status}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <div className="space-y-6">
          {selectedCountry ? (
            <>
              <section className="rounded-2xl border border-gray-200 bg-white p-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h3 className="text-xl font-semibold text-gray-900">
                      {selectedCountry.name_fr ?? selectedCountry.name_en ?? selectedCountry.code}
                    </h3>
                    <p className="mt-1 text-sm text-gray-500">
                      {selectedCountry.code} · {selectedCountry.currency} · {selectedContinentCode || 'continent à définir'}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={savingCountryCode === selectedCountry.code}
                      onClick={() =>
                        toggleCountry(selectedCountry, {
                          is_active: !selectedCountry.is_active,
                          launch_status: !selectedCountry.is_active ? 'ACTIVE' : 'SUSPENDED',
                        })
                      }
                      className={`rounded-xl px-4 py-2 text-sm font-medium ${
                        selectedCountry.is_active ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      {selectedCountry.is_active ? 'Marché actif' : 'Activer le marché'}
                    </button>
                    <button
                      type="button"
                      disabled={savingCountryCode === selectedCountry.code}
                      onClick={() => toggleCountry(selectedCountry, { signup_enabled: !selectedCountry.signup_enabled })}
                      className={`rounded-xl px-4 py-2 text-sm font-medium ${
                        selectedCountry.signup_enabled ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      {selectedCountry.signup_enabled ? 'Inscription ouverte' : 'Ouvrir l’inscription'}
                    </button>
                    <button
                      type="button"
                      disabled={savingCountryCode === selectedCountry.code}
                      onClick={() =>
                        toggleCountry(selectedCountry, {
                          food_delivery_enabled: !selectedCountry.food_delivery_enabled,
                        })
                      }
                      className={`rounded-xl px-4 py-2 text-sm font-medium ${
                        selectedCountry.food_delivery_enabled ? 'bg-violet-600 text-white' : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      {selectedCountry.food_delivery_enabled ? 'Food activé' : 'Activer food'}
                    </button>
                  </div>
                </div>
              </section>

              <section className="rounded-2xl border border-gray-200 bg-white p-5">
                <div className="mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">Activation modules par pays</h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Contrôlez ce qui est visible et opérationnel dans ce pays, module par module.
                  </p>
                </div>
                <div className="space-y-6">
                  {modulesByGroup.map(([group, items]) => (
                    <div key={group} className="space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-500">{group}</h4>
                        <span className="text-xs text-gray-400">{items.length} module(s)</span>
                      </div>
                      <div className="grid gap-3 lg:grid-cols-2">
                        {items.map((module) => {
                          const runtime = moduleRuntime[module.code];
                          const enabled = runtime?.enabled ?? module.default_enabled;
                          return (
                            <div key={module.code} className="rounded-2xl border border-gray-200 p-4">
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="font-semibold text-gray-900">{module.label}</p>
                                  <p className="mt-1 text-sm text-gray-500">{module.description}</p>
                                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                                    <span className="rounded-full bg-gray-100 px-2 py-1 text-gray-600">{module.code}</span>
                                    {runtime?.source ? (
                                      <span className="rounded-full bg-blue-50 px-2 py-1 text-blue-700">{runtime.source}</span>
                                    ) : null}
                                    {module.requires_country_active ? (
                                      <span className="rounded-full bg-amber-50 px-2 py-1 text-amber-700">dépend du marché</span>
                                    ) : null}
                                  </div>
                                </div>
                                <button
                                  type="button"
                                  disabled={savingModuleCode === module.code}
                                  onClick={() => void toggleModule(module.code, !enabled)}
                                  className={`rounded-xl px-3 py-2 text-xs font-semibold ${
                                    enabled ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-700'
                                  }`}
                                >
                                  {enabled ? 'Activé' : 'Désactivé'}
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="grid gap-6 xl:grid-cols-2">
                <div className="rounded-2xl border border-gray-200 bg-white p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">Pricing pays</h3>
                      <p className="mt-1 text-sm text-gray-500">
                        Définissez ici les prix de base VTC, livraison nourriture et livraison articles pour ce pays.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void loadCountryTemplate()}
                      className="rounded-xl border border-gray-200 px-3 py-2 text-xs font-medium hover:bg-gray-50"
                    >
                      Charger le template
                    </button>
                  </div>
                  <textarea
                    value={countryPricingDraft}
                    onChange={(event) => setCountryPricingDraft(event.target.value)}
                    className="mt-4 min-h-[360px] w-full rounded-2xl border border-gray-200 bg-gray-50 p-4 font-mono text-xs text-gray-800"
                  />
                  {countryPricingError ? <p className="mt-3 text-xs text-red-600">{countryPricingError}</p> : null}
                  <div className="mt-4 flex justify-end">
                    <button
                      type="button"
                      disabled={savingCountryPricing}
                      onClick={() => void saveCountryPricing()}
                      className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white"
                    >
                      {savingCountryPricing ? 'Sauvegarde...' : 'Enregistrer le pricing pays'}
                    </button>
                  </div>
                </div>

                <div className="rounded-2xl border border-gray-200 bg-white p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">Pricing continent</h3>
                      <p className="mt-1 text-sm text-gray-500">
                        Gardez ici un filet de sécurité continental qui sert de base avant les surcharges pays et zone.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void loadContinentTemplate()}
                      className="rounded-xl border border-gray-200 px-3 py-2 text-xs font-medium hover:bg-gray-50"
                    >
                      Charger le template
                    </button>
                  </div>
                  <div className="mt-3 rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-600">
                    Continent sélectionné : <span className="font-semibold text-gray-900">{selectedContinent?.code ?? '—'}</span>
                  </div>
                  <textarea
                    value={continentPricingDraft}
                    onChange={(event) => setContinentPricingDraft(event.target.value)}
                    className="mt-4 min-h-[324px] w-full rounded-2xl border border-gray-200 bg-gray-50 p-4 font-mono text-xs text-gray-800"
                  />
                  {continentPricingError ? <p className="mt-3 text-xs text-red-600">{continentPricingError}</p> : null}
                  <div className="mt-4 flex justify-end">
                    <button
                      type="button"
                      disabled={savingContinentPricing || !selectedContinentCode}
                      onClick={() => void saveContinentPricing()}
                      className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
                    >
                      {savingContinentPricing ? 'Sauvegarde...' : 'Enregistrer le pricing continent'}
                    </button>
                  </div>
                </div>
              </section>
            </>
          ) : (
            <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-10 text-sm text-gray-500">
              Sélectionnez un pays pour commencer.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
