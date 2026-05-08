import { useState } from 'react';
import { Button } from '../components/Button';
import { Avatar } from '../components/Avatar';
import { CheckCircle2, Star } from 'lucide-react';

interface CompletionScreenProps {
  onDone: () => void;
  taskerName?: string;
}

export function CompletionScreen({ onDone, taskerName = 'Votre prestataire' }: CompletionScreenProps) {
  const [rating, setRating] = useState(0);
  const [hoveredRating, setHoveredRating] = useState(0);

  return (
    <div className="h-full bg-white flex flex-col items-center justify-center px-8">
      <div className="w-20 h-20 rounded-full bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center mb-6 shadow-lg">
        <CheckCircle2 size={48} className="text-white" strokeWidth={3} />
      </div>

      <h2 className="text-3xl font-bold text-gray-900 mb-10">Tâche terminée</h2>

      <div className="w-full max-w-sm bg-gray-50 rounded-3xl p-6 mb-8">
        <h3 className="font-semibold text-gray-900 mb-5 text-center">Évaluez votre expérience</h3>

        <div className="flex items-center gap-3 mb-6 pb-6 border-b border-gray-200">
          <Avatar name={taskerName} size="md" />
          <div>
            <h4 className="font-semibold text-gray-900">{taskerName}</h4>
          </div>
        </div>

        <div className="flex justify-center gap-1.5 mb-2">
          {[1, 2, 3, 4, 5].map(star => (
            <button
              key={star}
              onClick={() => setRating(star)}
              onMouseEnter={() => setHoveredRating(star)}
              onMouseLeave={() => setHoveredRating(0)}
              className="transition-transform hover:scale-110 active:scale-95"
            >
              <Star
                size={44}
                className={
                  star <= (hoveredRating || rating)
                    ? 'fill-amber-400 text-amber-400'
                    : 'text-gray-300'
                }
                strokeWidth={2}
              />
            </button>
          ))}
        </div>
        <p className="text-center text-sm text-gray-500">
          {rating === 0 && 'Appuyez pour noter'}
          {rating === 1 && 'Mauvais'}
          {rating === 2 && 'Passable'}
          {rating === 3 && 'Bien'}
          {rating === 4 && 'Très bien'}
          {rating === 5 && 'Excellent'}
        </p>
      </div>

      <div className="w-full max-w-sm space-y-3">
        <Button fullWidth onClick={onDone} disabled={rating === 0}>
          Envoyer l'avis
        </Button>
        <button onClick={onDone} className="w-full text-gray-500 font-medium py-3 hover:text-gray-700 transition-colors">
          Passer
        </button>
      </div>
    </div>
  );
}
