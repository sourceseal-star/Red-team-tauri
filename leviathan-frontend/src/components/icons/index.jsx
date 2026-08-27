// Iconos comunes para LEVIATHAN Dashboard

export const Icons = {
  // Sistema
  leviathan: '🦑',
  commander: '⚡',
  arto: '🤖',
  seal: '🛡️',
  kraken: '💣',
  
  // Navegación
  dashboard: '📊',
  detection: '🎯',
  analysis: '🔬',
  exploit: '⚡',
  reports: '📋',
  settings: '⚙️',
  
  // Detección
  camera: '🎥',
  network: '🌐',
  port: '📡',
  osint: '🔍',
  
  // Análisis
  ai: '🤖',
  threatMap: '🗺️',
  stats: '📈',
  
  // Explotación
  exploitGeneric: '💥',
  exploitKraken: '💣',
  exploitChain: '🔄',
  
  // Estados
  success: '✓',
  error: '✗',
  warning: '⚠️',
  info: 'ℹ️',
  loading: '⏳',
  
  // Severidad
  critical: '💣',
  high: '⚠️',
  medium: 'ℹ️',
  low: '✓',
  
  // Acciones
  scan: '🔍',
  quickScan: '⚡',
  stop: '⏹️',
  play: '▶️',
  pause: '⏸️',
  refresh: '🔄',
  download: '📥',
  upload: '📤',
  delete: '🗑️',
  edit: '✏️',
  view: '👁️',
  
  // Protocolos
  http: '🌐',
  https: '🔒',
  rtsp: '🎥',
  onvif: '📹',
  ftp: '📁',
  ssh: '🔑',
  telnet: '📞',
  
  // Vendedores
  hikvision: '📹',
  dahua: '🎥',
  axis: '🌐',
  bosch: '🏢',
  
  // Objetos IA
  person: '👤',
  car: '🚗',
  phone: '📱',
  face: '😊',
  animal: '🐕',
  bag: '🛍️',
  weapon: '⚔️'
};

// Componente de icono
export const Icon = ({ name, size = '1rem', color, className = '' }) => {
  const icon = Icons[name] || '❓';
  return (
    <span 
      className={className} 
      style={{ 
        fontSize: size, 
        color: color || 'inherit'
      }}
    >
      {icon}
    </span>
  );
};

export default Icons;
