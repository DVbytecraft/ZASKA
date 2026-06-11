import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, PiggyBank, HeartPulse, ShieldCheck, Award } from 'lucide-react';
import { Card } from '../components/Card';
import { walletService } from '@zaska/shared-services';
import type { SocialProtectionOverview } from '@zaska/shared-services';
import { formatCurrency } from '../../services/fxService';

interface SocialProtectionScreenProps {
  onBack: () => void;
}

export function SocialProtectionScreen({ onBack }: SocialProtectionScreenProps) {
  const { t } = useTranslation();
  const [overview, setOverview] = useState<SocialProtectionOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  const load = useCallback(async () => {
    cancelledRef.current = false;
    setLoading(true);
    setError(null);
    try {
      const data = await walletService.getSocialProtectionOverview();
      if (!cancelledRef.current) setOverview(data);
    } catch (err) {
      if (!cancelledRef.current) setError(err instanceof Error ? err.message : t('socialProtection.errorLoad'));
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    cancelledRef.current = false;
    void load();
    return () => { cancelledRef.current = true; };
  }, [load]);

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">{t('socialProtection.title')}</h2>
        </div>
      </div>

      <div className="p-6">
        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 bg-gray-200 rounded-2xl animate-pulse" />
            ))}
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-50 border border-red-100 rounded-2xl p-4 text-center">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {!loading && !error && overview && (
          <>
            <Card className="mb-4 !border-0 bg-gradient-to-br from-[#6D28D9] to-[#5B21B6]">
              <div className="flex items-center gap-3 text-white">
                <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                  <Award size={24} />
                </div>
                <div>
                  <p className="font-semibold">{overview.badge.label}</p>
                  <p className="text-xs text-white/70">{overview.badge.description}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4 text-white">
                <div>
                  <p className="text-xs text-white/70">{t('socialProtection.completedTasks')}</p>
                  <p className="text-xl font-bold">{overview.total_completed_tasks}</p>
                </div>
                <div>
                  <p className="text-xs text-white/70">{t('socialProtection.activeMonths')}</p>
                  <p className="text-xl font-bold">{overview.active_months}</p>
                </div>
              </div>
            </Card>

            {overview.currencies.length === 0 && (
              <div className="bg-gray-100 rounded-2xl p-8 text-center">
                <p className="text-sm text-gray-500">{t('socialProtection.noData')}</p>
              </div>
            )}

            {overview.currencies.map((cur) => (
              <div key={cur.currency} className="mb-6">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">{cur.currency}</h3>

                <Card className="mb-3">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-purple-50 flex items-center justify-center">
                      <PiggyBank size={20} className="text-purple-600" />
                    </div>
                    <h4 className="font-semibold text-gray-900">{t('socialProtection.pension')}</h4>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">{t('socialProtection.totalContributed')}</span>
                      <span className="font-semibold text-gray-900">
                        {formatCurrency(parseFloat(cur.pension.total_contributed), cur.currency)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">{t('socialProtection.projectedPension')}</span>
                      <span className="font-semibold text-gray-900">
                        {formatCurrency(parseFloat(cur.pension.projected_monthly_pension), cur.currency)}
                      </span>
                    </div>
                    <div>
                      <div className="flex justify-between mb-1">
                        <span className="text-gray-500">{t('socialProtection.progressToGuarantee')}</span>
                        <span className="font-medium text-gray-900">{cur.pension.progress_percent_to_guarantee}%</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-purple-600 rounded-full"
                          style={{ width: `${Math.min(100, Math.max(0, cur.pension.progress_percent_to_guarantee))}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </Card>

                <Card className="mb-3">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center">
                      <HeartPulse size={20} className="text-green-600" />
                    </div>
                    <div className="flex-1 flex items-center justify-between">
                      <h4 className="font-semibold text-gray-900">{t('socialProtection.health')}</h4>
                      <span
                        className={`text-xs font-semibold px-2 py-1 rounded-full ${
                          cur.health.status === 'ACTIVE' ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {cur.health.status === 'ACTIVE' ? t('socialProtection.healthActive') : t('socialProtection.healthInactive')}
                      </span>
                    </div>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">{t('socialProtection.activeDays')}</span>
                      <span className="font-semibold text-gray-900">{cur.health.active_days_this_month}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">{t('socialProtection.totalPaidAuthorities')}</span>
                      <span className="font-semibold text-gray-900">
                        {formatCurrency(parseFloat(cur.health.total_paid_to_authorities), cur.currency)}
                      </span>
                    </div>
                  </div>
                </Card>

                <Card>
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center">
                      <ShieldCheck size={20} className="text-blue-600" />
                    </div>
                    <h4 className="font-semibold text-gray-900">{t('socialProtection.smoothing')}</h4>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">{t('socialProtection.availableBalance')}</span>
                      <span className="font-semibold text-gray-900">
                        {formatCurrency(parseFloat(cur.smoothing.available_balance), cur.currency)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">{t('socialProtection.totalContributed')}</span>
                      <span className="font-semibold text-gray-900">
                        {formatCurrency(parseFloat(cur.smoothing.total_contributed), cur.currency)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">{t('socialProtection.interestRedirected')}</span>
                      <span className="font-semibold text-gray-900">
                        {formatCurrency(parseFloat(cur.smoothing.interest_redirected_to_pension), cur.currency)}
                      </span>
                    </div>
                  </div>
                </Card>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
