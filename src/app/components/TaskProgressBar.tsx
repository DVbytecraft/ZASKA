interface TaskProgressBarProps {
  currentStatus: 'posted' | 'applications' | 'in_progress' | 'completed' | 'paid';
}

export function TaskProgressBar({ currentStatus }: TaskProgressBarProps) {
  const steps = [
    { id: 'posted', label: 'Posted' },
    { id: 'applications', label: 'Applications' },
    { id: 'in_progress', label: 'In progress' },
    { id: 'completed', label: 'Completed' },
    { id: 'paid', label: 'Paid' }
  ];

  const currentIndex = steps.findIndex(s => s.id === currentStatus);

  return (
    <div className="py-4">
      <div className="flex items-center justify-between mb-2">
        {steps.map((step, index) => (
          <div key={step.id} className="flex-1 flex items-center">
            <div className="flex flex-col items-center flex-1">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold transition-all ${
                index <= currentIndex
                  ? 'bg-[#6D28D9] text-white'
                  : 'bg-gray-200 text-gray-500'
              }`}>
                {index < currentIndex ? '✓' : index + 1}
              </div>
              <span className={`text-xs mt-1 font-medium ${
                index <= currentIndex ? 'text-gray-900' : 'text-gray-400'
              }`}>
                {step.label}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div className={`h-0.5 flex-1 mx-1 ${
                index < currentIndex ? 'bg-[#6D28D9]' : 'bg-gray-200'
              }`}></div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
