interface InputProps {
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  multiline?: boolean;
  rows?: number;
}

export function Input({ placeholder, value, onChange, type = 'text', multiline = false, rows = 4 }: InputProps) {
  const baseStyles = 'w-full px-4 py-3.5 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none focus:ring-4 focus:ring-[#6D28D9]/10 transition-all bg-white placeholder:text-gray-400';

  if (multiline) {
    return (
      <textarea
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        className={`${baseStyles} resize-none`}
      />
    );
  }

  return (
    <input
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={baseStyles}
    />
  );
}
