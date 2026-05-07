import { useState } from 'react';
import { ArrowLeft, DollarSign, TrendingUp, TrendingDown } from 'lucide-react';
import { Button } from '../components/Button';
import { Avatar } from '../components/Avatar';

interface PriceNegotiationScreenProps {
  taskerName: string;
  originalPrice: number;
  proposedPrice: number;
  onBack: () => void;
  onAccept: () => void;
  onCounter: (price: number) => void;
  onDecline: () => void;
}

export function PriceNegotiationScreen({
  taskerName,
  originalPrice,
  proposedPrice,
  onBack,
  onAccept,
  onCounter,
  onDecline
}: PriceNegotiationScreenProps) {
  const [counterPrice, setCounterPrice] = useState(originalPrice.toString());
  const [showCounterInput, setShowCounterInput] = useState(false);

  const priceDiff = proposedPrice - originalPrice;
  const isHigher = priceDiff > 0;

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">Price proposal</h2>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6">
          <div className="flex items-center gap-3 mb-6">
            <Avatar name={taskerName} size="md" />
            <div>
              <h4 className="font-semibold text-gray-900">{taskerName}</h4>
              <p className="text-sm text-gray-600">Sent a counter offer</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-xs text-gray-500 mb-1">Your budget</p>
              <p className="text-xl font-bold text-gray-900">${originalPrice}</p>
            </div>
            <div className={`rounded-xl p-4 ${isHigher ? 'bg-red-50' : 'bg-green-50'}`}>
              <p className="text-xs text-gray-500 mb-1">Proposed price</p>
              <div className="flex items-center gap-2">
                <p className={`text-xl font-bold ${isHigher ? 'text-red-600' : 'text-green-600'}`}>
                  ${proposedPrice}
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
              {isHigher ? '+' : ''}{priceDiff > 0 ? priceDiff : Math.abs(priceDiff)} difference
            </p>
          </div>
        </div>

        {!showCounterInput ? (
          <div className="space-y-3">
            <Button fullWidth onClick={onAccept}>
              Accept ${proposedPrice}
            </Button>
            <Button fullWidth variant="outline" onClick={() => setShowCounterInput(true)}>
              Make counter offer
            </Button>
            <button onClick={onDecline} className="w-full py-3 text-red-600 font-medium hover:text-red-700 transition-colors">
              Decline
            </button>
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Your counter offer</label>
            <div className="relative mb-4">
              <DollarSign size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="number"
                value={counterPrice}
                onChange={(e) => setCounterPrice(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-[#6D28D9]"
                placeholder="0"
              />
            </div>
            <div className="space-y-3">
              <Button fullWidth onClick={() => onCounter(parseFloat(counterPrice))}>
                Send offer
              </Button>
              <button onClick={() => setShowCounterInput(false)} className="w-full py-3 text-gray-600 font-medium hover:text-gray-900 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
