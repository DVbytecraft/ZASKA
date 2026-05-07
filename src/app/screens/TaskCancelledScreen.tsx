import { Button } from '../components/Button';
import { XCircle } from 'lucide-react';

interface TaskCancelledScreenProps {
  cancelledBy: 'user' | 'tasker';
  reason?: string;
  refundAmount?: string;
  onDone: () => void;
  onReportIssue?: () => void;
}

export function TaskCancelledScreen({
  cancelledBy,
  reason,
  refundAmount,
  onDone,
  onReportIssue
}: TaskCancelledScreenProps) {
  return (
    <div className="h-full flex flex-col items-center justify-center px-8 bg-white">
      <div className="w-20 h-20 rounded-full bg-orange-50 flex items-center justify-center mb-6">
        <XCircle size={40} className="text-orange-600" />
      </div>

      <h3 className="text-xl font-bold text-gray-900 mb-2 text-center">Task cancelled</h3>

      {cancelledBy === 'tasker' && (
        <p className="text-gray-600 text-center mb-8 max-w-xs text-sm">
          The tasker cancelled this task
          {reason && `: ${reason}`}
        </p>
      )}

      {cancelledBy === 'user' && (
        <p className="text-gray-600 text-center mb-8 max-w-xs text-sm">
          You cancelled this task
        </p>
      )}

      {refundAmount && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-8 max-w-sm w-full">
          <p className="text-sm text-green-900 text-center">
            <span className="font-bold">{refundAmount}</span> has been refunded to your wallet
          </p>
        </div>
      )}

      <div className="w-full max-w-sm space-y-3">
        <Button fullWidth onClick={onDone}>
          Back to home
        </Button>
        {cancelledBy === 'tasker' && onReportIssue && (
          <Button fullWidth variant="outline" onClick={onReportIssue}>
            Report issue
          </Button>
        )}
      </div>
    </div>
  );
}
