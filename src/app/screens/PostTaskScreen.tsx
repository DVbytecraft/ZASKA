import { useEffect, useState } from 'react';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { ArrowLeft, MapPin, Loader, AlertCircle } from 'lucide-react';
import { useTaskFlow, requestGeolocation } from '../hooks/useTaskFlow';
import { paymentService, apiClient } from '@zaska/shared-services';
import type { TaskMode } from '@zaska/shared-services';

interface PostTaskScreenProps {
  taskMode: TaskMode;
  onBack: () => void;
  onSubmit: (taskId: string) => void;
}

interface Coords {
  latitude: number;
  longitude: number;
}

export function PostTaskScreen({ taskMode, onBack, onSubmit }: PostTaskScreenProps) {
  const [step, setStep] = useState(1);
  const [description, setDescription] = useState('');
  const [budget, setBudget] = useState('');
  const [coords, setCoords] = useState<Coords | null>(null);
  const [coordsLoading, setCoordsLoading] = useState(false);
  const [coordsError, setCoordsError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { createTask, loading } = useTaskFlow();

  const currency = apiClient.getCurrency() ?? 'USD';

  useEffect(() => {
    if (step === 3) {
      setCoordsLoading(true);
      setCoordsError(null);
      requestGeolocation()
        .then((c) => setCoords(c))
        .catch(() => {
          setCoordsError('Location access denied. Please allow geolocation or enter manually.');
          // Fallback coords so user can still proceed
          setCoords({ latitude: 6.1375, longitude: 1.2123 });
        })
        .finally(() => setCoordsLoading(false));
    }
  }, [step]);

  const descriptionError = description.length > 0 && description.length < 10
    ? 'Describe your task in at least 10 characters'
    : null;

  const budgetNum = parseFloat(budget);
  const budgetError = budget.length > 0 && (isNaN(budgetNum) || budgetNum < 1)
    ? 'Enter a valid amount (minimum 1)'
    : null;

  const canProceed = () => {
    if (step === 1) return description.length >= 10;
    if (step === 2) return budget.length > 0 && !isNaN(budgetNum) && budgetNum >= 1;
    if (step === 3) return coords !== null;
    return false;
  };

  const handleNext = async () => {
    if (step < 3) {
      setStep(step + 1);
      return;
    }

    if (!coords) {
      setSubmitError('Location is required to post a task.');
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
        currency,
      });

      if (!task?.id) throw new Error('Task creation failed — no ID returned');

      // Create escrow (non-blocking: task is posted even if payment intent fails)
      try {
        await paymentService.createIntent(task.id);
      } catch {
        // Escrow will be created on the next eligible operation
      }

      onSubmit(task.id);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to create task. Please try again.');
    }
  };

  const stepLabels = ['Describe', 'Budget', 'Location'];

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3 mb-4">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-gray-900">Post a task</h2>
            <p className="text-sm text-gray-500">Step {step} of 3 — {stepLabels[step - 1]}</p>
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
        {step === 1 && (
          <div>
            <h3 className="text-xl font-bold text-gray-900 mb-1">Describe your task</h3>
            <p className="text-sm text-gray-500 mb-6">What do you need help with?</p>
            <Input
              placeholder="e.g., Clean my apartment, pick up groceries, assemble furniture…"
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
              {description.length} chars{description.length < 10 ? ` (${10 - description.length} more needed)` : ''}
            </p>
          </div>
        )}

        {step === 2 && (
          <div>
            <h3 className="text-xl font-bold text-gray-900 mb-1">Set your budget</h3>
            <p className="text-sm text-gray-500 mb-6">How much are you willing to pay?</p>
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
                <span className="font-semibold">Typical range:</span>{' '}
                {currency === 'XOF' || currency === 'XAF'
                  ? '5,000 – 25,000 ' + currency
                  : '25 – 75 ' + currency}
              </p>
            </div>
            {taskMode === 'choose' && (
              <p className="text-xs text-gray-500">
                Taskers can apply at this budget or propose a different price
              </p>
            )}
          </div>
        )}

        {step === 3 && (
          <div>
            <h3 className="text-xl font-bold text-gray-900 mb-1">Confirm location</h3>
            <p className="text-sm text-gray-500 mb-6">We'll use your current location</p>

            <div className="bg-gradient-to-br from-gray-50 to-gray-100 border-2 border-gray-200 rounded-2xl h-48 flex items-center justify-center mb-4 relative overflow-hidden">
              <div className="text-center relative z-10">
                {coordsLoading ? (
                  <>
                    <div className="w-16 h-16 bg-[#6D28D9]/20 rounded-2xl flex items-center justify-center mx-auto mb-3">
                      <Loader size={32} className="text-[#6D28D9] animate-spin" />
                    </div>
                    <p className="font-semibold text-gray-700">Detecting location…</p>
                  </>
                ) : coords ? (
                  <>
                    <div className="w-16 h-16 bg-[#6D28D9] rounded-2xl flex items-center justify-center mx-auto mb-3 shadow-lg">
                      <MapPin size={32} className="text-white" strokeWidth={2.5} />
                    </div>
                    <p className="font-semibold text-gray-900">
                      {coords.latitude.toFixed(4)}, {coords.longitude.toFixed(4)}
                    </p>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {coordsError ? 'Approximate location (GPS unavailable)' : 'Current location'}
                    </p>
                  </>
                ) : null}
              </div>
            </div>

            {coordsError && (
              <div className="bg-amber-50 border border-amber-100 rounded-xl p-3 flex items-start gap-2">
                <AlertCircle size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-800">{coordsError}</p>
              </div>
            )}
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
          disabled={!canProceed() || loading || (step === 3 && coordsLoading)}
        >
          {loading ? 'Creating task…' : step === 3 ? 'Post task' : 'Next'}
        </Button>
      </div>
    </div>
  );
}
