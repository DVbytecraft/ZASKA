import { useEffect, useMemo, useState } from "react";
import { marketplaceApi, type CityOption, type CountryOption, type GeoSuggestion, type TargetLocationValue } from "../services/marketplaceApi";

interface TargetLocationPickerProps {
  storageKey: string;
  defaultCountryCode?: string | null;
  title?: string;
  description?: string;
  allowModeToggle?: boolean;
  onChange?: (value: TargetLocationValue) => void;
}

function normalizeCountryLabel(country: CountryOption) {
  return country.nameFr ?? country.name_fr ?? country.nameEn ?? country.name_en ?? country.code;
}

function countryPrimaryCity(country: CountryOption) {
  return country.primaryCityName ?? country.primary_city_name ?? "";
}

export function TargetLocationPicker({
  storageKey,
  defaultCountryCode,
  title = "Zone ciblée",
  description = "Choisissez le pays, la ville et l’adresse de la personne ou de la zone visée.",
  allowModeToggle = true,
  onChange,
}: TargetLocationPickerProps) {
  const [countries, setCountries] = useState<CountryOption[]>([]);
  const [cities, setCities] = useState<CityOption[]>([]);
  const [suggestions, setSuggestions] = useState<GeoSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  const [value, setValue] = useState<TargetLocationValue>(() => {
    const stored = localStorage.getItem(storageKey);
    if (stored) {
      try {
        return JSON.parse(stored) as TargetLocationValue;
      } catch {
        /* ignore */
      }
    }
    return {
      mode: "local",
      countryCode: defaultCountryCode ?? "",
      cityName: "",
      address: "",
      latitude: null,
      longitude: null,
    };
  });

  useEffect(() => {
    let active = true;
    marketplaceApi.getGeoCountries({ active_only: true }).then((res) => {
      if (!active || !res.success) return;
      setCountries(res.data);
      if (!value.countryCode && defaultCountryCode) {
        const fallback = res.data.find((item) => item.code === defaultCountryCode);
        if (fallback) {
          setValue((prev) => ({
            ...prev,
            countryCode: fallback.code,
            cityName: prev.cityName || countryPrimaryCity(fallback),
          }));
        }
      }
    });
    return () => {
      active = false;
    };
  }, [defaultCountryCode]);

  useEffect(() => {
    if (!value.countryCode) {
      setCities([]);
      return;
    }
    let active = true;
    marketplaceApi.getGeoCities({ country_code: value.countryCode, active_only: true }).then((res) => {
      if (!active || !res.success) return;
      setCities(res.data);
      if (!value.cityName) {
        const primary = res.data.find((city) => city.is_primary) ?? res.data[0];
        if (primary) {
          setValue((prev) => ({ ...prev, cityName: prev.cityName || primary.name }));
        }
      }
    });
    return () => {
      active = false;
    };
  }, [value.countryCode]);

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(value));
    onChange?.(value);
  }, [value, storageKey, onChange]);

  useEffect(() => {
    if (value.address.trim().length < 3 || !value.countryCode) {
      setSuggestions([]);
      return;
    }
    let active = true;
    setLoadingSuggestions(true);
    const timer = window.setTimeout(() => {
      void marketplaceApi
        .autocompletePlaces({
          query: value.address,
          country_code: value.countryCode,
          city_name: value.cityName || undefined,
          limit: 6,
        })
        .then((res) => {
          if (!active) return;
          if (res.success) {
            setSuggestions(res.data.results);
          }
        })
        .finally(() => {
          if (active) setLoadingSuggestions(false);
        });
    }, 300);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [value.address, value.countryCode, value.cityName]);

  const selectedCountry = useMemo(
    () => countries.find((country) => country.code === value.countryCode) ?? null,
    [countries, value.countryCode],
  );

  const updateValue = (patch: Partial<TargetLocationValue>) => {
    setValue((prev) => ({ ...prev, ...patch }));
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 space-y-4">
      <div>
        <h3 className="text-base font-semibold text-gray-900">{title}</h3>
        <p className="text-sm text-gray-500 mt-1">{description}</p>
      </div>

      {allowModeToggle && (
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            className={`rounded-xl px-3 py-2 text-sm font-medium border ${value.mode === "local" ? "bg-black text-white border-black" : "bg-white text-gray-700 border-gray-200"}`}
            onClick={() => updateValue({ mode: "local" })}
          >
            Commande locale
          </button>
          <button
            type="button"
            className={`rounded-xl px-3 py-2 text-sm font-medium border ${value.mode === "remote" ? "bg-black text-white border-black" : "bg-white text-gray-700 border-gray-200"}`}
            onClick={() => updateValue({ mode: "remote" })}
          >
            Pour quelqu’un d’autre
          </button>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Pays</label>
          <select
            className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm"
            value={value.countryCode}
            onChange={(e) =>
              updateValue({
                countryCode: e.target.value,
                cityName: "",
                address: "",
                latitude: null,
                longitude: null,
              })}
          >
            <option value="">Sélectionner un pays actif</option>
            {countries.map((country) => (
              <option key={country.code} value={country.code}>
                {normalizeCountryLabel(country)}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Ville</label>
          <select
            className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm"
            value={value.cityName}
            onChange={(e) => updateValue({ cityName: e.target.value })}
            disabled={!value.countryCode}
          >
            <option value="">{selectedCountry ? "Sélectionner une ville" : "Choisir d’abord un pays"}</option>
            {cities.map((city) => (
              <option key={city.id} value={city.name}>
                {city.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Adresse ou quartier</label>
        <input
          type="text"
          className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm"
          placeholder="Ex: Paris 11e, Lomé Tokoin, Cotonou Haie Vive"
          value={value.address}
          onChange={(e) =>
            updateValue({
              address: e.target.value,
              latitude: null,
              longitude: null,
            })}
        />
        {loadingSuggestions && <p className="text-xs text-gray-400 mt-1">Recherche de suggestions...</p>}
        {!loadingSuggestions && suggestions.length > 0 && (
          <div className="mt-2 rounded-xl border border-gray-200 overflow-hidden">
            {suggestions.map((item, index) => (
              <button
                key={`${item.label}-${index}`}
                type="button"
                className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 border-b last:border-b-0"
                onClick={() =>
                  updateValue({
                    address: item.label,
                    cityName: item.cityName ?? value.cityName,
                    latitude: item.latitude ?? null,
                    longitude: item.longitude ?? null,
                  })}
              >
                {item.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-600">
        <span className="font-semibold text-gray-800">Cible active :</span>{" "}
        {[normalizeCountryLabel(selectedCountry ?? { code: value.countryCode } as CountryOption), value.cityName, value.address]
          .filter(Boolean)
          .join(" · ") || "Aucune zone cible sélectionnée"}
      </div>
    </div>
  );
}
