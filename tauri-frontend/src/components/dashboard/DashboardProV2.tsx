import { lazy, Suspense } from 'react';
import WarRoom from './WarRoom';

export default function DashboardProV2() {
  return (
    <div className="h-screen w-full bg-[var(--ss-bg)] text-gray-200 font-mono">
      <WarRoom />
    </div>
  );
}
