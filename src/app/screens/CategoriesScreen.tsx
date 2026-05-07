import { Card } from '../components/Card';
import { ArrowLeft, Sparkles, Package, FileText, Users, Heart, Car, Wrench, GraduationCap } from 'lucide-react';

interface CategoriesScreenProps {
  onBack: () => void;
  onSelectCategory: (category: string) => void;
}

export function CategoriesScreen({ onBack, onSelectCategory }: CategoriesScreenProps) {
  const categories = [
    { id: 'cleaning', name: 'Cleaning', icon: Sparkles, color: 'from-purple-500 to-purple-600', tasks: 234 },
    { id: 'delivery', name: 'Delivery', icon: Package, color: 'from-blue-500 to-blue-600', tasks: 189 },
    { id: 'admin', name: 'Admin Tasks', icon: FileText, color: 'from-green-500 to-green-600', tasks: 145 },
    { id: 'personal', name: 'Personal Help', icon: Heart, color: 'from-pink-500 to-pink-600', tasks: 167 },
    { id: 'moving', name: 'Moving', icon: Car, color: 'from-orange-500 to-orange-600', tasks: 98 },
    { id: 'handyman', name: 'Handyman', icon: Wrench, color: 'from-yellow-500 to-yellow-600', tasks: 123 },
    { id: 'tutoring', name: 'Tutoring', icon: GraduationCap, color: 'from-indigo-500 to-indigo-600', tasks: 76 },
    { id: 'other', name: 'Other', icon: Users, color: 'from-gray-500 to-gray-600', tasks: 201 }
  ];

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Categories</h2>
            <p className="text-sm text-gray-600">Browse tasks by category</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        <div className="grid grid-cols-2 gap-4">
          {categories.map(category => {
            const Icon = category.icon;
            return (
              <Card
                key={category.id}
                onClick={() => onSelectCategory(category.id)}
                className="hover:shadow-lg transition-all"
              >
                <div className="flex flex-col items-center py-6">
                  <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${category.color} flex items-center justify-center mb-3 shadow-lg`}>
                    <Icon size={28} className="text-white" strokeWidth={2.5} />
                  </div>
                  <span className="font-semibold text-gray-900 text-center mb-1">{category.name}</span>
                  <span className="text-xs text-gray-500">{category.tasks} tasks</span>
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
