interface ZaskaLogoProps {
  size?: number;
  showText?: boolean;
  textClassName?: string;
  className?: string;
}

export function ZaskaLogo({ size = 64, showText = false, textClassName = 'text-white', className = '' }: ZaskaLogoProps) {
  return (
    <div className={`flex flex-col items-center gap-2 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 100 100"
        xmlns="http://www.w3.org/2000/svg"
        style={{ display: 'block', flexShrink: 0 }}
      >
        <defs>
          <linearGradient id="zaska-bg" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#8B5CF6" />
            <stop offset="100%" stopColor="#5B21B6" />
          </linearGradient>
        </defs>
        {/* Rounded-square background */}
        <rect width="100" height="100" rx="22" fill="url(#zaska-bg)" />
        {/* Bold Z — top bar + diagonal + bottom bar, each with right-pointing arrow tip */}
        <path
          d="M26,20 L64,20 L76,31 L64,42 L43,59 L64,59 L76,70 L64,81 L26,81 L26,59 L47,42 L26,42 Z"
          fill="white"
        />
        {/* Left orange speed diamond */}
        <polygon points="15,51 25,46 35,51 25,56" fill="#F97316" />
        {/* Right orange speed diamond */}
        <polygon points="65,51 75,46 85,51 75,56" fill="#F97316" />
      </svg>
      {showText && (
        <span className={`font-extrabold tracking-tight leading-none ${textClassName}`} style={{ fontSize: Math.round(size * 0.42) }}>
          ZASKA
        </span>
      )}
    </div>
  );
}
