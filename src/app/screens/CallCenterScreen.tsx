import { Headphones } from 'lucide-react';

export function CallCenterScreen() {
  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      <div className="px-6 pt-8 pb-6 bg-gradient-to-br from-[#1E40AF] to-[#1E3A8A]">
        <h1 className="text-2xl font-bold text-white mb-1">Call Center</h1>
        <p className="text-white/75 text-sm">Support requests and account issues</p>
      </div>

      <div className="flex flex-col items-center justify-center py-20 text-center px-6">
        <Headphones size={48} className="text-gray-300 mb-4" />
        <p className="text-lg font-semibold text-gray-700">Aucun ticket</p>
        <p className="text-sm text-gray-500 mt-2">
          Le module de gestion des tickets support sera disponible dans une prochaine version.
        </p>
      </div>
    </div>
  );
}
