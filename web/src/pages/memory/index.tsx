import Spotlight from '@/components/spotlight';
import { Outlet } from 'react-router';
import { SideBar } from './sidebar';

export default function MemoryWrapper() {
  return (
    <section className="flex h-full w-full flex-col pt-3">
      <div className="flex min-h-0 flex-1">
        <SideBar />
        <div className="relative mb-5 mr-5 flex-1 overflow-auto rounded-md border-[0.5px] border-border-button p-5">
          <Spotlight opcity={0.18} coverage={42} className="opacity-40" />
          <Outlet />
        </div>
      </div>
    </section>
  );
}
