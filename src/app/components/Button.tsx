interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
  disabled?: boolean;
}

export function Button({
  children,
  onClick,
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  disabled = false
}: ButtonProps) {
  const baseStyles = 'rounded-xl transition-all duration-200 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed';

  const variants = {
    primary: 'bg-[#6D28D9] text-white shadow-lg shadow-[#6D28D9]/25 hover:bg-[#5B21B6] hover:shadow-xl hover:shadow-[#6D28D9]/30',
    secondary: 'bg-[#1E40AF] text-white shadow-lg shadow-[#1E40AF]/25 hover:bg-[#1E3A8A] hover:shadow-xl hover:shadow-[#1E40AF]/30',
    outline: 'bg-white border-2 border-gray-200 text-gray-900 hover:border-[#6D28D9] hover:text-[#6D28D9] hover:bg-[#6D28D9]/5'
  };

  const sizes = {
    sm: 'px-4 py-2.5 text-sm font-semibold',
    md: 'px-5 py-3 text-sm font-semibold',
    lg: 'px-6 py-3.5 text-base font-semibold'
  };

  const widthClass = fullWidth ? 'w-full' : '';

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${widthClass}`}
    >
      {children}
    </button>
  );
}
