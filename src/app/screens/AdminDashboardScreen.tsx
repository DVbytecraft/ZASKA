import { Card } from '../components/Card';
import { TrendingUp, Users, DollarSign, AlertTriangle, CheckCircle, Clock } from 'lucide-react';

export function AdminDashboardScreen() {
  const metrics = [
    { label: 'Tasks today', value: '147', change: '+12%', icon: CheckCircle, color: 'green' },
    { label: 'Revenue', value: '$4,235', change: '+8%', icon: DollarSign, color: 'purple' },
    { label: 'Active users', value: '1,249', change: '+23%', icon: Users, color: 'blue' },
    { label: 'Disputes', value: '3', change: '-2', icon: AlertTriangle, color: 'red' }
  ];

  const recentTasks = [
    { id: 1, task: 'Grocery shopping', client: 'John D.', tasker: 'Sarah J.', amount: '$25', status: 'completed' },
    { id: 2, task: 'Clean apartment', client: 'Mary S.', tasker: 'Michael C.', amount: '$45', status: 'in_progress' },
    { id: 3, task: 'Move furniture', client: 'Alex M.', tasker: 'Emily D.', amount: '$60', status: 'posted' }
  ];

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      <div className="px-6 pt-8 pb-6 bg-gradient-to-br from-[#6D28D9] to-[#5B21B6]">
        <h1 className="text-2xl font-bold text-white mb-1">Admin Dashboard</h1>
        <p className="text-white/75 text-sm">Platform overview and metrics</p>
      </div>

      <div className="px-6 py-4">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">Key metrics</h3>
        <div className="grid grid-cols-2 gap-3 mb-6">
          {metrics.map(metric => {
            const Icon = metric.icon;
            const colors = {
              green: 'from-green-500 to-emerald-600',
              purple: 'from-purple-500 to-purple-600',
              blue: 'from-blue-500 to-blue-600',
              red: 'from-red-500 to-red-600'
            };

            return (
              <Card key={metric.label}>
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colors[metric.color as keyof typeof colors]} flex items-center justify-center mb-3`}>
                  <Icon size={20} className="text-white" strokeWidth={2.5} />
                </div>
                <p className="text-xs text-gray-500 mb-1">{metric.label}</p>
                <div className="flex items-baseline gap-2">
                  <p className="text-2xl font-bold text-gray-900">{metric.value}</p>
                  <span className={`text-xs font-semibold ${
                    metric.change.startsWith('+') ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {metric.change}
                  </span>
                </div>
              </Card>
            );
          })}
        </div>

        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">Recent activity</h3>
        <div className="space-y-2">
          {recentTasks.map(task => (
            <Card key={task.id} className="hover:shadow-lg transition-all">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold text-gray-900">{task.task}</h4>
                <span className={`text-xs font-semibold px-2 py-1 rounded-lg ${
                  task.status === 'completed' ? 'bg-green-50 text-green-700' :
                  task.status === 'in_progress' ? 'bg-blue-50 text-blue-700' :
                  'bg-gray-50 text-gray-700'
                }`}>
                  {task.status.replace('_', ' ')}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <div className="text-gray-600">
                  <span>{task.client}</span>
                  <span className="text-gray-400 mx-2">→</span>
                  <span>{task.tasker}</span>
                </div>
                <span className="font-semibold text-gray-900">{task.amount}</span>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
