import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { MapPin, Clock, Zap } from 'lucide-react';

interface TaskerModeScreenProps {
  onApply?: () => void;
}

export function TaskerModeScreen({ onApply }: TaskerModeScreenProps = {}) {
  const tasks = [
    { id: 1, title: 'Grocery shopping', location: '0.3 mi', time: '2h', price: '25', urgent: false },
    { id: 2, title: 'Clean apartment', location: '0.7 mi', time: '3h', price: '45', urgent: true },
    { id: 3, title: 'Move furniture', location: '1.2 mi', time: '4h', price: '60', urgent: false },
    { id: 4, title: 'Dog walking', location: '0.5 mi', time: '1h', price: '20', urgent: false }
  ];

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      <div className="px-6 pt-8 pb-8 bg-gradient-to-br from-[#1E40AF] to-[#1E3A8A]">
        <h1 className="text-2xl font-bold text-white mb-1">Available tasks</h1>
        <p className="text-white/75 text-sm">Accept tasks and start earning</p>
      </div>

      <div className="px-6 py-4 space-y-3">
        {tasks.map(task => (
          <Card key={task.id} className="hover:shadow-lg transition-all">
            <div className="flex items-start justify-between mb-3">
              <h3 className="text-base font-semibold text-gray-900 flex-1">{task.title}</h3>
              {task.urgent && (
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-50 text-red-700 rounded-lg text-xs font-semibold ml-2">
                  <Zap size={12} fill="currentColor" />
                  Urgent
                </span>
              )}
            </div>

            <div className="flex items-center gap-4 mb-4 text-sm text-gray-600">
              <div className="flex items-center gap-1.5">
                <MapPin size={15} strokeWidth={2.5} />
                <span>{task.location}</span>
              </div>
              <span className="text-gray-300">•</span>
              <div className="flex items-center gap-1.5">
                <Clock size={15} strokeWidth={2.5} />
                <span>{task.time}</span>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-gray-900">${task.price}</span>
                  <span className="text-xs text-gray-500">budget</span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">Or propose your price</p>
              </div>
              <Button size="md" onClick={onApply}>Apply</Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
