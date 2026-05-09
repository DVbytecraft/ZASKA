type ProgressStatus = 'posted' | 'applications' | 'in_progress' | 'validation' | 'paid';

interface TaskProgressBarProps {
  currentStatus: ProgressStatus;
}

export function TaskProgressBar({ currentStatus }: TaskProgressBarProps) {
  const steps: { id: ProgressStatus; label: string }[] = [
    { id: 'posted',       label: 'Publiée' },
    { id: 'applications', label: 'Candidats' },
    { id: 'in_progress',  label: 'En cours' },
    { id: 'validation',   label: 'Validation' },
    { id: 'paid',         label: 'Payée' },
  ];

  const currentIndex = steps.findIndex(s => s.id === currentStatus);

  return (
    <div className="py-4">
      <div className="flex items-center justify-between">
        {steps.map((step, index) => (
          <div key={step.id} className="flex-1 flex items-center">
            <div className="flex flex-col items-center flex-1">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-all ${
                index < currentIndex
                  ? 'bg-[#6D28D9] text-white'
                  : index === currentIndex
                  ? 'bg-[#6D28D9] text-white ring-4 ring-[#6D28D9]/20'
                  : 'bg-gray-200 text-gray-500'
              }`}>
                {index <= currentIndex ? '✓' : index + 1}
              </div>
              <span className={`text-[10px] mt-1 font-medium text-center leading-tight ${
                index <= currentIndex ? 'text-gray-900' : 'text-gray-400'
              }`}>
                {step.label}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div className={`h-0.5 flex-1 mx-1 mb-4 ${
                index < currentIndex ? 'bg-[#6D28D9]' : 'bg-gray-200'
              }`} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
