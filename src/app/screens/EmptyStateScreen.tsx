import { Button } from '../components/Button';
import { Inbox } from 'lucide-react';

interface EmptyStateScreenProps {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyStateScreen({ title, message, actionLabel, onAction }: EmptyStateScreenProps) {
  return (
    <div className="h-full flex flex-col items-center justify-center px-8 bg-gray-50">
      <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mb-6">
        <Inbox size={40} className="text-gray-400" />
      </div>

      <h3 className="text-xl font-bold text-gray-900 mb-2 text-center">{title}</h3>
      <p className="text-gray-600 text-center mb-8 max-w-xs">{message}</p>

      {actionLabel && onAction && (
        <Button onClick={onAction}>{actionLabel}</Button>
      )}
    </div>
  );
}
