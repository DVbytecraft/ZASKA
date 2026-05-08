import { useState } from 'react';
import { ArrowLeft, TrendingUp, TrendingDown } from 'lucide-react';
import { Button } from '../components/Button';
import { Avatar } from '../components/Avatar';

interface PriceNegotiationScreenProps {
  taskerName: string;
  originalPrice: number;
  proposedPrice: number;
  currency?: string;
  onBack: () => void;
  onAccept: () => void;
  onCounter: (price: number) => void;
  onDecline: () => void;
}

export function PriceNegotiationScreen({
  taskerName,
  originalPrice,
  proposedPrice,
  currency = 'CFA',
  onBack,
  onAccept,
  onCounter,
  onDecline,
}: PriceNegotiationScreenProps) {
  const [counterPrice, setCounterPrice] = useState(originalPrice.toString());
  const [showCounterInput, setShowCounterInput] = useState(false);

  const priceDiff = proposedPrice - originalPrice;
  const isHigher = priceDiff > 0;
  const diffAbs = Math.abs(priceDiff);

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">Proposition de prix</h2>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6">
          <div className="flex items-center gap-3 mb-6">
            <Avatar name={taskerName} size="md" />
            <div>
              <h4 className="font-semibold text-gray-900">{taskerName}</h4>
              <p className="text-sm text-gray-600">a envoyé une contre-offre</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-xs text-gray-500 mb-1">Votre budget</p>
              <p className="text-xl font-bold text-gray-900">{currency} {originalPrice}</p>
            </div>
            <div className={`rounded-xl p-4 ${isHigher ? 'bg-red-50' : 'bg-green-50'}`}>
              <p className="text-xs text-gray-500 mb-1">Prix proposé</p>
              <div className="flex items-center gap-2">
                <p className={`text-xl font-bold ${isHigher ? 'text-red-600' : 'text-green-600'}`}>
                  {currency} {proposedPrice}
                </p>
                {isHigher ? (
                  <TrendingUp size={16} className="text-red-600" />
                ) : (
                  <TrendingDown size={16} className="text-green-600" />
                )}
              </div>
            </div>
          </div>

          <div className={`border rounded-xl p-3 ${
            isHigher ? 'border-red-200 bg-red-50' : 'border-green-200 bg-green-50'
          }`}>
            <p className={`text-sm font-medium ${isHigher ? 'text-red-900' : 'text-green-900'}`}>
              {isHigher ? '+' : '-'}{diffAbs} {currency} de différence
            </p>
          </div>
        </div>

        {!showCounterInput ? (
          <div className="space-y-3">
            <Button fullWidth onClick={onAccept}>
              Accepter {currency} {proposedPrice}
            </Button>
            <Button fullWidth variant="outline" onClick={() => setShowCounterInput(true)}>
              Faire une contre-offre
            </Button>
            <button
              onClick={onDecline}
              className="w-full py-3 text-red-600 font-medium hover:text-red-700 transition-colors"
            >
              Refuser
            </button>
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Votre contre-offre ({currency})</label>
            <div className="relative mb-4">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 font-semibold text-sm">
                {currency}
              </span>
              <input
                type="number"
                value={counterPrice}
                onChange={(e) => setCounterPrice(e.target.value)}
                className="w-full pl-16 pr-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-[#6D28D9] text-lg font-semibold"
                placeholder="0"
              />
            </div>
            <div className="space-y-3">
              <Button fullWidth onClick={() => onCounter(parseFloat(counterPrice))}>
                Envoyer l'offre
              </Button>
              <button
                onClick={() => setShowCounterInput(false)}
                className="w-full py-3 text-gray-600 font-medium hover:text-gray-900 transition-colors"
              >
                Annuler
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
