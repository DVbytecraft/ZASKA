import { Loader2 } from 'lucide-react';

interface LoadingScreenProps {
  message?: string;
}

export function LoadingScreen({ message = 'Loading...' }: LoadingScreenProps) {
  return (
    <div className="h-full flex flex-col items-center justify-center px-8 bg-white">
      <Loader2 size={48} className="text-[#6D28D9] animate-spin mb-4" strokeWidth={2.5} />
      <p className="text-gray-600">{message}</p>
    </div>
  );
}
