import { useMemo } from 'react';
import { fxService, formatCurrency } from '../../services/fxService';
import { useFxRates, useViewerCurrency } from '../hooks/useFxRates';
import { useTranslation } from 'react-i18next';

interface PriceDisplayProps {
  amount: number;
  currency: string;
  /** If true, renders a compact single-line layout */
  compact?: boolean;
  className?: string;
}

export function PriceDisplay({ amount, currency, compact = false, className = '' }: PriceDisplayProps) {
  const { t } = useTranslation();
  const rates = useFxRates();
  const viewerCurrency = useViewerCurrency();

  const primary = formatCurrency(amount, currency);

  const converted = useMemo(() => {
    if (!rates || viewerCurrency === currency.toUpperCase()) return null;
    const result = fxService.convert(amount, currency, viewerCurrency, rates);
    return formatCurrency(result, viewerCurrency);
  }, [rates, amount, currency, viewerCurrency]);

  if (compact) {
    return (
      <span className={`inline-flex items-baseline gap-1.5 ${className}`}>
        <span className="font-semibold">{primary}</span>
        {converted && (
          <span className="text-gray-400 text-xs">
            {t('fx.equiv')} {converted}
          </span>
        )}
      </span>
    );
  }

  return (
    <div className={`flex flex-col ${className}`}>
      <span className="font-semibold text-gray-900">{primary}</span>
      {converted && (
        <span className="text-xs text-gray-500 mt-0.5">
          {t('fx.equiv')} {converted}
        </span>
      )}
    </div>
  );
}
