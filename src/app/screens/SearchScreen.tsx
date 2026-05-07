import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Search, AlertCircle } from 'lucide-react';
import { Card } from '../components/Card';
import { taskService } from '@zaska/shared-services';
import type { Task } from '@zaska/shared-services';

interface SearchScreenProps {
  onBack: () => void;
  onTaskDetail?: (taskId: string) => void;
}

function useDebounce(value: string, ms: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

export function SearchScreen({ onBack, onTaskDetail }: SearchScreenProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounced = useDebounce(query, 400);

  useEffect(() => {
    if (!debounced.trim()) {
      setResults([]);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    taskService.listTasks()
      .then((tasks) => {
        const q = debounced.toLowerCase();
        setResults(
          tasks.filter(
            (t) =>
              t.title.toLowerCase().includes(q) ||
              t.description.toLowerCase().includes(q)
          )
        );
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Search failed'))
      .finally(() => setLoading(false));
  }, [debounced]);

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 border-b border-gray-200">
        <div className="flex items-center gap-3 mb-4">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors" aria-label="Go back">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div className="flex-1 relative">
            <Search size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              ref={inputRef}
              type="text"
              placeholder="Search tasks..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
              aria-label="Search tasks"
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none"
            />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-gray-200 rounded-2xl animate-pulse" />)}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-40 gap-2">
            <AlertCircle size={32} className="text-red-400" />
            <p className="text-sm text-red-500">{error}</p>
          </div>
        ) : results.length > 0 ? (
          <div className="space-y-3">
            {results.map((task) => (
              <Card
                key={task.id}
                onClick={() => onTaskDetail?.(task.id)}
                className="hover:shadow-md transition-all cursor-pointer"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold text-gray-900 truncate">{task.title}</h4>
                    <p className="text-sm text-gray-500 truncate mt-0.5">{task.description}</p>
                  </div>
                  <span className="text-sm font-bold text-[#6D28D9] whitespace-nowrap">
                    {Number(task.price).toLocaleString()} {task.currency}
                  </span>
                </div>
              </Card>
            ))}
          </div>
        ) : query.trim() ? (
          <div className="flex flex-col items-center justify-center h-40 text-gray-400">
            <Search size={36} className="mb-2 text-gray-200" />
            <p className="text-sm">No tasks found for "{query}"</p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-40 text-gray-400">
            <Search size={36} className="mb-2 text-gray-200" />
            <p className="text-sm">Type to search tasks.</p>
          </div>
        )}
      </div>
    </div>
  );
}
