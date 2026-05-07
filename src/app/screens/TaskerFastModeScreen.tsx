import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { MapPin, Clock, Zap, DollarSign } from 'lucide-react';

interface TaskerFastModeScreenProps {
  onAccept?: () => void;
}

export function TaskerFastModeScreen({ onAccept }: TaskerFastModeScreenProps = {}) {
  const tasks = [
    { id: 1, title: 'Grocery shopping', location: '0.3 mi', time: '2h', price: '25', mode: 'fast', urgent: false },
    { id: 2, title: 'Clean apartment', location: '0.7 mi', time: '3h', price: '45', mode: 'choose', urgent: true },
    { id: 3, title: 'Pick up package', location: '0.5 mi', time: '1h', price: '15', mode: 'fast', urgent: false },
    { id: 4, title: 'Move furniture', location: '1.2 mi', time: '4h', price: '60', mode: 'choose', urgent: false }
  ];

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      <div className="px-6 pt-8 pb-8 bg-gradient-to-br from-[#1E40AF] to-[#1E3A8A]">
        <h1 className="text-2xl font-bold text-white mb-1">Tasks near you</h1>
        <p className="text-white/75 text-sm">Accept or apply to earn money</p>
      </div>

      <div className="px-6 py-4">
        <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-3 mb-4">
          <div className="flex items-center gap-2">
            <Zap size={18} className="text-amber-600" fill="currentColor" />
            <p className="text-sm text-amber-900 font-medium">
              <span className="font-bold">Fast mode</span> tasks are first-come, first-served
            </p>
          </div>
        </div>

        <div className="space-y-3">
          {tasks.map(task => (
            <Card key={task.id} className="hover:shadow-lg transition-all">
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-base font-semibold text-gray-900 flex-1">{task.title}</h3>
                <div className="flex flex-col gap-1.5 items-end ml-2">
                  {task.mode === 'fast' && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gradient-to-r from-amber-400 to-orange-500 text-white text-xs font-bold rounded-full">
                      <Zap size={10} fill="white" />
                      FAST
                    </span>
                  )}
                  {task.urgent && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-50 text-red-700 rounded-lg text-xs font-semibold">
                      <Zap size={12} fill="currentColor" />
                      Urgent
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-4 mb-3 text-sm text-gray-600">
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

              <div className="bg-gray-50 rounded-xl p-3 mb-3">
                <div className="flex items-center gap-2">
                  <DollarSign size={18} className="text-gray-600" />
                  <span className="text-2xl font-bold text-gray-900">${task.price}</span>
                  <span className="text-sm text-gray-500">total</span>
                </div>
              </div>

              {task.mode === 'fast' ? (
                <Button fullWidth onClick={onAccept} variant="primary">
                  <Zap size={18} className="mr-2" fill="white" />
                  Accept now
                </Button>
              ) : (
                <div className="space-y-2">
                  <Button fullWidth onClick={onAccept}>
                    Apply to task
                  </Button>
                  <p className="text-xs text-center text-gray-500">You can propose your own price</p>
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
