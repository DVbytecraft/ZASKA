import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { Avatar } from '../components/Avatar';
import { ArrowLeft, Star, MapPin, CheckCircle } from 'lucide-react';

interface TaskerListScreenProps {
  onBack: () => void;
  onSelect: () => void;
}

export function TaskerListScreen({ onBack, onSelect }: TaskerListScreenProps) {
  const taskers: never[] = [];

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3 mb-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Available taskers</h2>
            <p className="text-sm text-gray-500">{taskers.length} taskers found</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4 space-y-3">
        {taskers.map(tasker => (
          <Card key={tasker.id} className="hover:shadow-xl transition-all">
            <div className="flex items-start gap-4">
              <div className="relative">
                <Avatar name={tasker.name} size="lg" />
                {tasker.verified && (
                  <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center border-2 border-white">
                    <CheckCircle size={12} className="text-white" fill="white" />
                  </div>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="font-semibold text-gray-900">{tasker.name}</h4>
                </div>

                <div className="flex items-center gap-3 text-sm mb-2">
                  <div className="flex items-center gap-1">
                    <Star size={14} className="fill-amber-400 text-amber-400" />
                    <span className="font-semibold text-gray-900">{tasker.rating}</span>
                    <span className="text-gray-500">({tasker.reviews})</span>
                  </div>
                  <span className="text-gray-300">•</span>
                  <div className="flex items-center gap-1 text-gray-600">
                    <MapPin size={14} />
                    <span>{tasker.distance}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-2xl font-bold text-gray-900">${tasker.price}</span>
                    <span className="text-sm text-gray-500 ml-1">total</span>
                  </div>
                  <Button size="md" onClick={onSelect}>
                    Select
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
