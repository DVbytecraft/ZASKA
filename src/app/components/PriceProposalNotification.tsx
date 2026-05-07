import { Button } from './Button';
import { Card } from './Card';
import { Avatar } from './Avatar';
import { TrendingDown, TrendingUp, X } from 'lucide-react';

interface PriceProposalNotificationProps {
  taskerName: string;
  originalPrice: number;
  proposedPrice: number;
  onAccept: () => void;
  onReject: () => void;
  onDismiss: () => void;
}

export function PriceProposalNotification({
  taskerName,
  originalPrice,
  proposedPrice,
  onAccept,
  onReject,
  onDismiss
}: PriceProposalNotificationProps) {
  const isLower = proposedPrice < originalPrice;
  const difference = Math.abs(proposedPrice - originalPrice);
  const percentChange = Math.round((difference / originalPrice) * 100);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50 p-4">
      <Card className="max-w-md w-full animate-slide-up">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <Avatar name={taskerName} size="md" />
            <div>
              <h4 className="font-semibold text-gray-900">Price proposal</h4>
              <p className="text-sm text-gray-500">{taskerName}</p>
            </div>
          </div>
          <button onClick={onDismiss} className="p-1 hover:bg-gray-100 rounded-full">
            <X size={20} className="text-gray-500" />
          </button>
        </div>

        <div className="bg-gray-50 rounded-xl p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-sm text-gray-600 mb-1">Your budget</p>
              <p className="text-xl font-bold text-gray-400 line-through">${originalPrice}</p>
            </div>
            <div className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-semibold ${
              isLower ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
            }`}>
              {isLower ? (
                <>
                  <TrendingDown size={16} />
                  <span>-{percentChange}%</span>
                </>
              ) : (
                <>
                  <TrendingUp size={16} />
                  <span>+{percentChange}%</span>
                </>
              )}
            </div>
          </div>

          <div>
            <p className="text-sm text-gray-600 mb-1">Proposed price</p>
            <p className="text-3xl font-bold text-gray-900">${proposedPrice}</p>
          </div>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          {isLower
            ? `${taskerName} is offering to complete this task for less than your budget.`
            : `${taskerName} would like to charge more than your original budget for this task.`}
        </p>

        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={onReject}
            className="px-4 py-3 border-2 border-gray-200 rounded-xl font-semibold text-gray-900 hover:bg-gray-50 transition-all"
          >
            Reject
          </button>
          <Button onClick={onAccept}>
            Accept ${proposedPrice}
          </Button>
        </div>
      </Card>
    </div>
  );
}
