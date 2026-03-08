interface HealthHubLogoProps {
  size?: 'sm' | 'md' | 'lg';
}

export function HealthHubLogo({ size = 'md' }: HealthHubLogoProps) {
  const textClass =
    size === 'sm' ? 'text-lg' : size === 'lg' ? 'text-4xl' : 'text-2xl';
  const hubPadding =
    size === 'sm' ? 'px-2 py-0.5' : size === 'lg' ? 'px-3 py-1' : 'px-2.5 py-0.5';
  const dotSize =
    size === 'sm' ? 'w-2.5 h-2.5' : size === 'lg' ? 'w-4 h-4' : 'w-3 h-3';

  return (
    <div className={`flex items-center select-none ${textClass}`}>
      <span style={{ color: '#1F2937', fontWeight: 700, letterSpacing: '-0.3px' }}>
        Health
      </span>
      <div className="relative ml-1">
        <div
          className={`flex items-center rounded-full ${hubPadding}`}
          style={{ background: 'linear-gradient(135deg, #1B9A7A 0%, #1B6B45 100%)' }}
        >
          <span className="text-white font-bold" style={{ letterSpacing: '-0.3px' }}>
            Hub
          </span>
        </div>
        <div
          className={`absolute -top-1 -right-1 ${dotSize} rounded-full border-2 border-white`}
          style={{ backgroundColor: '#F59E0B' }}
        />
      </div>
    </div>
  );
}
