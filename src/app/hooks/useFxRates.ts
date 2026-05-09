import { useState, useEffect } from 'react';
import { fxService } from '../../services/fxService';
import { apiClient } from '@zaska/shared-services';
import { getCountry } from '../config/countries';

export function useFxRates() {
  const [rates, setRates] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    fxService.getRates().then(setRates).catch(() => {});
  }, []);

  return rates;
}

/** Returns the viewer's currency code from their stored country code. */
export function useViewerCurrency(): string {
  const countryCode = apiClient.getCountryCode();
  if (!countryCode) return 'XOF';
  const country = getCountry(countryCode);
  return country?.currency ?? 'XOF';
}
