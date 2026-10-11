import ListFilterBar from '@/components/list-filter-bar';
import { t } from 'i18next';
import { useFetchMemoryMessageList, useSelectFilters } from './hook';
import { MemoryTable } from './message-table';

export default function MemoryMessage() {
  const {
    searchString,
    data,
    pagination,
    handleInputChange,
    setPagination,
    filterValue,
    handleFilterSubmit,
    loading,
  } = useFetchMemoryMessageList();
  const { filters } = useSelectFilters();
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <ListFilterBar
        title={t('memory.messages.pageTitle')}
        onSearchChange={handleInputChange}
        searchString={searchString}
        filters={filters}
        onChange={handleFilterSubmit}
        value={filterValue}
        leftPanel={
          <div className="items-start">
            <div className="pb-1">{t('memory.sideBar.messages')}</div>
            <div className="text-sm font-normal text-text-secondary">
              {t('memory.messages.messageDescription')}
            </div>
          </div>
        }
      />
      <MemoryTable
        messages={data?.messages?.message_list ?? []}
        pagination={pagination}
        setPagination={setPagination}
        total={data?.messages?.total_count ?? 0}
        loading={loading}
      />
    </div>
  );
}
