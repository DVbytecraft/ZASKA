interface CardProps {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}

export function Card({ children, onClick, className = '' }: CardProps) {
  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-2xl p-4 shadow-sm border border-gray-100 transition-all ${
        onClick ? 'cursor-pointer hover:shadow-md active:scale-[0.99]' : ''
      } ${className}`}
    >
      {children}
    </div>
  );
}
