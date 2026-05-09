import { apiClient } from '@zaska/shared-services';

interface FxRatesResponse {
  base: 'USD';
  rates: Record<string, number>;
  updated_at: string;
}

// Supported currencies in ZASKA markets
export type SupportedCurrency = 'XOF' | 'XAF' | 'GHS' | 'NGN' | 'KES' | 'EUR' | 'USD';

// Cache rates in-memory with a 5-minute TTL
let _cachedRates: Record<string, number> | null = null;
let _cacheExpiresAt = 0;
const CACHE_TTL_MS = 5 * 60 * 1000;

// Fallback rates (1 USD = X currency) used if API is unavailable
const FALLBACK_RATES: Record<string, number> = {
  USD: 1,
  XOF: 620,
  XAF: 620,
  GHS: 15.5,
  NGN: 1650,
  KES: 130,
  EUR: 0.92,
};

export const fxService = {
  async getRates(): Promise<Record<string, number>> {
    if (_cachedRates && Date.now() < _cacheExpiresAt) {
      return _cachedRates;
    }
    try {
      const resp = await apiClient.get<FxRatesResponse>('/fx/rates');
      _cachedRates = { ...FALLBACK_RATES, ...resp.rates };
      _cacheExpiresAt = Date.now() + CACHE_TTL_MS;
      return _cachedRates;
    } catch {
      return FALLBACK_RATES;
    }
  },

  /** Convert amount between two currencies via USD pivot. */
  convert(amount: number, from: string, to: string, rates: Record<string, number>): number {
    if (from === to) return amount;
    const rateFrom = rates[from.toUpperCase()] ?? 1;
    const rateTo = rates[to.toUpperCase()] ?? 1;
    const usd = amount / rateFrom;
    return usd * rateTo;
  },

  /** Force invalidate the cache (e.g. after admin sets a new rate). */
  invalidateCache() {
    _cachedRates = null;
    _cacheExpiresAt = 0;
  },
};

/** Currency symbol map for display. */
export const CURRENCY_SYMBOLS: Record<string, string> = {
  XOF: 'FCFA',
  XAF: 'FCFA',
  GHS: 'GH₵',
  NGN: '₦',
  KES: 'KSh',
  EUR: '€',
  USD: '$',
};

/** Format an amount for display (e.g. "5 000 FCFA" or "€12.50"). */
export function formatCurrency(amount: number, currency: string): string {
  const symbol = CURRENCY_SYMBOLS[currency.toUpperCase()] ?? currency;
  const isPrefix = ['EUR', 'USD', 'GHS'].includes(currency.toUpperCase());

  const locale = ['XOF', 'XAF', 'EUR'].includes(currency.toUpperCase()) ? 'fr-FR' : 'en-US';
  const decimals = ['XOF', 'XAF', 'NGN'].includes(currency.toUpperCase()) ? 0 : 2;

  const formatted = amount.toLocaleString(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return isPrefix ? `${symbol} ${formatted}` : `${formatted} ${symbol}`;
}
