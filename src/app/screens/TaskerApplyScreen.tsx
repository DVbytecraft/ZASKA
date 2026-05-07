import { useState, useEffect } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { taskService } from '@zaska/shared-services';
import { ArrowLeft } from 'lucide-react';

interface TaskerApplyScreenProps {
  taskId: string;
  taskBudget?: number;
  taskCurrency?: string;
  onBack: () => void;
  onSubmit: () => void;
}

export function TaskerApplyScreen({
  taskId,
  taskBudget: budgetProp,
  taskCurrency: currencyProp,
  onBack,
  onSubmit,
}: TaskerApplyScreenProps) {
  const [applyType, setApplyType] = useState<'accept' | 'propose'>('accept');
  const [proposedPrice, setProposedPrice] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taskBudget, setTaskBudget] = useState<number>(budgetProp ?? 0);
  const [taskCurrency, setTaskCurrency] = useState<string>(currencyProp ?? 'XOF');

  useEffect(() => {
    if (budgetProp !== undefined) return;
    taskService.getTask(taskId)
      .then((t) => {
        setTaskBudget(Number(t.price));
        setTaskCurrency(t.currency);
      })
      .catch(() => {});
  }, [taskId, budgetProp]);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      await taskService.applyTask(taskId, {
        proposed_price: applyType === 'propose' && proposedPrice ? Number(proposedPrice) : undefined,
        currency: taskCurrency,
        message: message || undefined,
      });
      onSubmit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit application');
    } finally {
      setLoading(false);
    }
  };

  const canSubmit = applyType === 'accept' || (proposedPrice.length > 0 && Number(proposedPrice) > 0);

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Apply to task</h2>
            <p className="text-sm text-gray-500">Choose your pricing option</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="space-y-3 mb-6">
          <div
            onClick={() => setApplyType('accept')}
            className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
              applyType === 'accept'
                ? 'border-[#6D28D9] bg-[#6D28D9]/5 shadow-md'
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-gray-900">Accept client budget</h4>
              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                applyType === 'accept' ? 'border-[#6D28D9]' : 'border-gray-300'
              }`}>
                {applyType === 'accept' && <div className="w-3 h-3 bg-[#6D28D9] rounded-full"></div>}
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900">{taskCurrency} {taskBudget}</span>
            </div>
            <p className="text-xs text-green-600 mt-2 font-medium">✓ Recommended — higher selection chance</p>
          </div>

          <div
            onClick={() => setApplyType('propose')}
            className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
              applyType === 'propose'
                ? 'border-[#6D28D9] bg-[#6D28D9]/5 shadow-md'
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-semibold text-gray-900">Propose your price</h4>
              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                applyType === 'propose' ? 'border-[#6D28D9]' : 'border-gray-300'
              }`}>
                {applyType === 'propose' && <div className="w-3 h-3 bg-[#6D28D9] rounded-full"></div>}
              </div>
            </div>
            {applyType === 'propose' && (
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xl text-gray-400 font-semibold">$</span>
                <input
                  type="number"
                  placeholder="0.00"
                  value={proposedPrice}
                  onChange={(e) => setProposedPrice(e.target.value)}
                  className="w-full pl-8 pr-4 py-3 text-xl font-semibold rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none transition-colors bg-white"
                />
              </div>
            )}
            <p className="text-xs text-amber-600 mt-2 font-medium">⚠ Client may reject if price is too different</p>
          </div>
        </div>

        <div className="mb-4">
          <label className="text-sm font-medium text-gray-700 mb-2 block">Message (optional)</label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Introduce yourself or explain why you're a great fit..."
            rows={3}
            maxLength={500}
            className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm resize-none"
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-100 rounded-xl p-3 mb-4">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        <Card className="bg-blue-50 border-blue-100">
          <h4 className="font-semibold text-blue-900 mb-2">Tips for applying</h4>
          <ul className="text-sm text-blue-900 space-y-1">
            <li>• Accepting the budget increases selection chances</li>
            <li>• You can only apply once per task</li>
            <li>• Client sees your profile when reviewing applications</li>
          </ul>
        </Card>
      </div>

      <div className="px-6 py-4 bg-white border-t border-gray-200">
        <Button fullWidth onClick={handleSubmit} disabled={!canSubmit || loading}>
          {loading ? 'Submitting...' : 'Submit application'}
        </Button>
      </div>
    </div>
  );
}
