import { RAGFlowAvatar } from '@/components/ragflow-avatar';
import { Button } from '@/components/ui/button';
import { useSecondPathName } from '@/hooks/route-hook';
import { cn } from '@/lib/utils';
import { Routes } from '@/routes';
import { formatPureDate } from '@/utils/date';
import { MemoryStick, Settings } from 'lucide-react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useFetchMemoryBaseConfiguration } from '../hooks/use-memory-setting';
import { useHandleMenuClick } from './hooks';

export function SideBar() {
  const pathName = useSecondPathName();
  const { handleMenuClick } = useHandleMenuClick();
  const { data } = useFetchMemoryBaseConfiguration();
  const { t } = useTranslation();

  const items = useMemo(() => {
    return [
      {
        icon: <MemoryStick className="size-4" />,
        label: t(`memory.sideBar.messages`),
        key: Routes.MemoryMessage,
      },
      {
        icon: <Settings className="size-4" />,
        label: t(`memory.sideBar.configuration`),
        key: Routes.MemorySetting,
      },
    ];
  }, [t]);

  return (
    <aside className="relative w-[min(100%,13rem)] shrink-0 space-y-8 p-4 sm:p-5">
      <div className="flex max-w-full items-center gap-2.5">
        <RAGFlowAvatar
          avatar={data.avatar}
          name={data.name}
          className="size-12 shrink-0 sm:size-16"
        />
        <div className="space-y-1 overflow-hidden text-xs text-text-secondary">
          <h3 className="line-clamp-1 overflow-hidden text-ellipsis text-base font-semibold text-text-primary sm:text-lg">
            {data.name}
          </h3>
          <div className="flex justify-between">
            <span className="truncate">{data.description}</span>
          </div>
          <div>
            {t('memory.config.created')} {formatPureDate(data.create_time)}
          </div>
        </div>
      </div>

      <div className="flex w-full flex-col gap-3">
        {items.map((item) => {
          const active = '/' + pathName === item.key;
          return (
            <Button
              key={item.key}
              variant={active ? 'secondary' : 'ghost'}
              className={cn(
                'relative h-11 w-full justify-start gap-2.5 px-3 text-text-secondary',
                {
                  'bg-bg-card': active,
                  'text-text-primary': active,
                },
              )}
              onClick={handleMenuClick(item.key)}
            >
              {item.icon}
              <span>{item.label}</span>
            </Button>
          );
        })}
      </div>
    </aside>
  );
}
