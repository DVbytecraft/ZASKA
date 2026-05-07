interface SkeletonLoadingScreenProps {
  type?: 'list' | 'detail' | 'chat';
}

export function SkeletonLoadingScreen({ type = 'list' }: SkeletonLoadingScreenProps) {
  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50 animate-pulse">
      {type === 'list' && (
        <div className="px-6 py-4 space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="bg-white rounded-2xl p-4 border border-gray-100">
              <div className="flex items-start gap-3">
                <div className="w-12 h-12 bg-gray-200 rounded-full flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-3/4" />
                  <div className="h-3 bg-gray-200 rounded w-1/2" />
                  <div className="h-3 bg-gray-200 rounded w-2/3" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {type === 'detail' && (
        <div className="px-6 py-6 space-y-6">
          <div className="bg-white rounded-2xl p-6">
            <div className="h-6 bg-gray-200 rounded w-2/3 mb-4" />
            <div className="h-4 bg-gray-200 rounded w-full mb-2" />
            <div className="h-4 bg-gray-200 rounded w-5/6" />
          </div>

          <div className="bg-white rounded-2xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-16 h-16 bg-gray-200 rounded-full" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-gray-200 rounded w-1/3" />
                <div className="h-3 bg-gray-200 rounded w-1/4" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6">
            <div className="h-4 bg-gray-200 rounded w-1/4 mb-3" />
            <div className="h-10 bg-gray-200 rounded" />
          </div>
        </div>
      )}

      {type === 'chat' && (
        <div className="px-4 py-4 space-y-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className={`flex ${i % 2 === 0 ? 'justify-end' : 'justify-start'}`}>
              <div className={`${i % 2 === 0 ? 'bg-gray-200' : 'bg-gray-100'} rounded-2xl px-4 py-3 max-w-[75%]`}>
                <div className="h-3 bg-gray-300 rounded w-32 mb-1" />
                <div className="h-2 bg-gray-300 rounded w-16" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
