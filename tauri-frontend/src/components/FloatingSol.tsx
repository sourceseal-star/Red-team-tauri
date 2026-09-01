import { useEffect, useState } from 'react';

export const FloatingSol = () => {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (window.location.pathname.includes('sol.html')) return;
    const t = setTimeout(() => setVisible(true), 800);
    return () => clearTimeout(t);
  }, []);

  if (!visible) return null;
  return (
    <button
      onClick={() => window.open('/sol.html', '_blank')}
      aria-label="Abrir Sol"
      className="fixed bottom-6 right-6 z-[9999] w-14 h-14 rounded-full
                 bg-gradient-to-br from-amber-400 to-orange-500 text-2xl
                 shadow-[0_4px_24px_rgba(245,158,11,0.5)] hover:scale-110
                 active:scale-95 transition-transform"
    >☀️</button>
  );
};
