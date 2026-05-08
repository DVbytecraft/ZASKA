import { useState } from 'react';
import { ArrowLeft, AlertCircle, Camera } from 'lucide-react';
import { Button } from '../components/Button';

interface ReportIssueScreenProps {
  onBack: () => void;
  onSubmit: () => void;
  taskId?: string;
}

export function ReportIssueScreen({ onBack, onSubmit, taskId }: ReportIssueScreenProps) {
  const [category, setCategory] = useState('');
  const [description, setDescription] = useState('');

  const issueCategories = [
    'Tâche non effectuée',
    'Travail de mauvaise qualité',
    'Prestataire absent',
    'Problème de paiement',
    'Problème de sécurité',
    'Autre',
  ];

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-xl font-semibold text-gray-900">Signaler un problème</h2>
          <div className="w-10" />
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {taskId && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6 flex items-start gap-3">
            <AlertCircle size={20} className="text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-blue-900">Tâche ID : {taskId}</p>
              <p className="text-sm text-blue-700">Notre équipe examinera votre signalement dans les 24 heures</p>
            </div>
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Catégorie du problème</label>
            <div className="grid grid-cols-2 gap-2">
              {issueCategories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setCategory(cat)}
                  className={`py-3 px-4 border-2 rounded-xl text-sm font-medium transition-all ${
                    category === cat
                      ? 'border-[#6D28D9] bg-purple-50 text-[#6D28D9]'
                      : 'border-gray-200 text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#6D28D9] focus:border-transparent resize-none"
              placeholder="Décrivez le problème en détail…"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Joindre des photos (facultatif)
            </label>
            <button className="w-full py-8 border-2 border-dashed border-gray-300 rounded-xl hover:border-gray-400 transition-colors">
              <Camera size={32} className="mx-auto mb-2 text-gray-400" />
              <p className="text-sm font-medium text-gray-600">Importer des photos</p>
            </button>
          </div>
        </div>
      </div>

      <div className="p-6 border-t border-gray-200">
        <Button fullWidth onClick={onSubmit} disabled={!category || !description}>
          Envoyer le signalement
        </Button>
      </div>
    </div>
  );
}
