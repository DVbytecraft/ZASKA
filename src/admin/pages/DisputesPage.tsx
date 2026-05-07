import { AlertTriangle } from 'lucide-react';

export function DisputesPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Litiges</h2>
        <p className="text-sm text-gray-600">Résolution des conflits entre utilisateurs et taskers</p>
      </div>

      <div className="flex flex-col items-center justify-center py-20 text-center">
        <AlertTriangle size={48} className="text-gray-300 mb-4" />
        <p className="text-lg font-semibold text-gray-700">Aucun litige</p>
        <p className="text-sm text-gray-500 mt-2 max-w-sm">
          Le système de gestion des litiges sera disponible dans une prochaine version. Aucune donnée fictive.
        </p>
      </div>
    </div>
  );
}
