import {
  ConfirmDeleteDialog,
  ConfirmDeleteDialogNode,
} from '@/components/confirm-delete-dialog';
import { EmptyType } from '@/components/empty/constant';
import Empty from '@/components/empty/empty';
import { Button } from '@/components/ui/button';
import { Modal } from '@/components/ui/modal/modal';
import { RAGFlowPagination } from '@/components/ui/ragflow-pagination';
import { Spin } from '@/components/ui/spin';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { RunningStatus } from '@/constants/knowledge';
import { Pagination } from '@/interfaces/common';
import { cn } from '@/lib/utils';
import ProcessLogModal, {
  ILogInfo,
  replaceText,
} from '@/pages/dataset/process-log-modal';
import { MessageTypeOptions } from '@/pages/memories/constants';
import {
  ColumnDef,
  ColumnFiltersState,
  ExpandedState,
  Row,
  SortingState,
  VisibilityState,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getExpandedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table';
import dayjs from 'dayjs';
import { t } from 'i18next';
import { pick } from 'lodash';
import {
  Copy,
  Eraser,
  ListChevronsDownUp,
  ListChevronsUpDown,
  TextSelect,
} from 'lucide-react';
import * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { CopyToClipboard } from 'react-copy-to-clipboard';
import { useMessageAction } from './hook';
import { IMessageInfo } from './interface';

export type MemoryTableProps = {
  messages: Array<IMessageInfo>;
  total: number;
  pagination: Pagination;
  setPagination: (params: { page: number; pageSize: number }) => void;
  loading?: boolean;
};

const columnHelper = createColumnHelper<IMessageInfo>();

function getTaskStatus(progress: number) {
  if (progress >= 1) {
    return RunningStatus.DONE;
  } else if (progress > 0 && progress < 1) {
    return RunningStatus.RUNNING;
  } else {
    return RunningStatus.FAIL;
  }
}

function getTaskStatusLabel(status: RunningStatus) {
  if (status === RunningStatus.DONE) {
    return t('memory.messages.taskStatusDone');
  }
  if (status === RunningStatus.RUNNING) {
    return t('memory.messages.taskStatusRunning');
  }
  return t('memory.messages.taskStatusFailed');
}

type UpdateMessageStateFn = (
  message: IMessageInfo,
  enable: boolean,
) => Promise<boolean>;

function StatusSwitch({
  row,
  disabled,
  onUpdate,
}: {
  row: Row<IMessageInfo>;
  disabled: boolean;
  onUpdate: UpdateMessageStateFn;
}) {
  const serverStatus = row.original.status;
  const [optimisticStatus, setOptimisticStatus] = useState(serverStatus);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    setOptimisticStatus(serverStatus);
  }, [serverStatus]);

  const label = optimisticStatus
    ? t('memory.messages.disableMessage')
    : t('memory.messages.enableMessage');

  return (
    <div className="flex min-h-11 min-w-11 items-center justify-start">
      <Switch
        disabled={disabled || pending}
        checked={optimisticStatus}
        aria-label={`${label}: ${row.original.session_id}`}
        className="m-2"
        onCheckedChange={(val) => {
          setOptimisticStatus(val);
          setPending(true);
          onUpdate(row.original, val).then((success) => {
            setPending(false);
            if (!success) {
              setOptimisticStatus(serverStatus);
            }
          });
        }}
      />
    </div>
  );
}

export function MemoryTable({
  messages,
  total,
  pagination,
  setPagination,
  loading = false,
}: MemoryTableProps) {
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>(
    [],
  );
  const [columnVisibility, setColumnVisibility] =
    React.useState<VisibilityState>({});
  const [copied, setCopied] = useState(false);
  const {
    showDeleteDialog,
    setShowDeleteDialog,
    handleClickDeleteMessage,
    selectedMessage,
    handleDeleteMessage,
    handleClickUpdateMessageState,
    selectedMessageContent,
    showMessageContentDialog,
    setShowMessageContentDialog,
    handleClickMessageContentDialog,
  } = useMessageAction();

  const disabledRowFunc = (row: Row<IMessageInfo>) => {
    return row.original.forget_at !== 'None' && !!row.original.forget_at;
  };

  const [isModalVisible, setIsModalVisible] = useState(false);
  const [logInfo, setLogInfo] = useState<ILogInfo>();
  const showLog = React.useCallback((row: Row<IMessageInfo>) => {
    const task = row.original.task;
    const logDetail = {
      startTime: dayjs(task.create_time)
        .locale(document.documentElement.lang)
        .format('MM/DD/YYYY HH:mm:ss'),
      status: getTaskStatus(task.progress),
      details: task.progress_msg,
    } as unknown as ILogInfo;
    setLogInfo(logDetail);
    setIsModalVisible(true);
  }, []);

  const messageTypeOptions = useMemo(() => MessageTypeOptions(t), []);

  const columns: ColumnDef<IMessageInfo>[] = useMemo(
    () => [
      {
        accessorKey: 'session_id',
        header: ({ table }) => (
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="min-h-11 min-w-11"
              aria-label={
                table.getIsAllRowsExpanded()
                  ? t('memory.messages.collapseAll')
                  : t('memory.messages.expandAll')
              }
              onClick={table.getToggleAllRowsExpandedHandler()}
            >
              {table.getIsAllRowsExpanded() ? (
                <ListChevronsDownUp size={16} />
              ) : (
                <ListChevronsUpDown size={16} />
              )}
            </Button>
            <span>{t('memory.messages.sessionId')}</span>
          </div>
        ),
        cell: ({ row }) => (
          <div className="flex items-center gap-1">
            {row.getCanExpand() ? (
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="min-h-11 min-w-11"
                aria-label={
                  row.getIsExpanded()
                    ? t('memory.messages.collapseRow')
                    : t('memory.messages.expandRow')
                }
                onClick={row.getToggleExpandedHandler()}
              >
                {row.getIsExpanded() ? (
                  <ListChevronsDownUp size={16} />
                ) : (
                  <ListChevronsUpDown size={16} />
                )}
              </Button>
            ) : null}
            <div
              className={cn('text-sm font-medium', {
                'pl-5': !row.getCanExpand(),
              })}
            >
              {row.getValue('session_id')}
            </div>
          </div>
        ),
      },
      {
        accessorKey: 'agent_name',
        header: () => <span>{t('memory.messages.agent')}</span>,
        cell: ({ row }) => (
          <div className="text-sm font-medium">
            {row.getValue('agent_name')}
          </div>
        ),
      },
      {
        accessorKey: 'message_type',
        header: () => <span>{t('memory.messages.type')}</span>,
        cell: ({ row }) => {
          const value = row.getValue('message_type') as string;
          const label =
            messageTypeOptions.find((item) => item.value === value)?.label ??
            value;
          return <div className="text-sm font-medium capitalize">{label}</div>;
        },
      },
      {
        accessorKey: 'valid_at',
        header: () => <span>{t('memory.messages.validDate')}</span>,
        cell: ({ row }) => (
          <div className="text-sm">{row.getValue('valid_at')}</div>
        ),
      },
      {
        accessorKey: 'forget_at',
        header: () => <span>{t('memory.messages.forgetAt')}</span>,
        cell: ({ row }) => (
          <div className="text-sm">{row.getValue('forget_at')}</div>
        ),
      },
      {
        accessorKey: 'status',
        header: () => <span>{t('memory.messages.enable')}</span>,
        cell: ({ row }) => (
          <StatusSwitch
            row={row}
            disabled={disabledRowFunc(row)}
            onUpdate={handleClickUpdateMessageState}
          />
        ),
      },
      columnHelper.display({
        id: 'task_progress',
        cell: ({ row }) => {
          const { task } = row.original;
          if (!task) {
            return null;
          }
          const taskStatus = getTaskStatus(task.progress);
          const statusLabel = getTaskStatusLabel(taskStatus);
          return (
            <Button
              type="button"
              variant="transparent"
              size="icon"
              className="size-11 min-h-11 min-w-11 border-0"
              aria-label={`${t('memory.messages.viewTaskLog')}: ${statusLabel}`}
              title={`${t('memory.messages.viewTaskLog')}: ${statusLabel}`}
              onClick={() => showLog(row)}
            >
              <span className="sr-only">{statusLabel}</span>
              <div
                className={cn('size-2 rounded-full', {
                  'bg-state-success': taskStatus === RunningStatus.DONE,
                  'bg-state-error': taskStatus === RunningStatus.FAIL,
                  'bg-state-warning': taskStatus === RunningStatus.RUNNING,
                })}
              />
            </Button>
          );
        },
      }),
      {
        accessorKey: 'action',
        header: () => <span>{t('memory.messages.action')}</span>,
        meta: {
          cellClassName: 'w-28',
        },
        cell: ({ row }) => (
          <div className="flex items-center gap-1 opacity-100">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="min-h-11 min-w-11 bg-transparent"
              aria-label={t('memory.messages.viewContent')}
              title={t('memory.messages.viewContent')}
              onClick={() => {
                handleClickMessageContentDialog(row.original);
              }}
            >
              <TextSelect />
            </Button>
            <Button
              type="button"
              variant="delete"
              size="icon"
              disabled={disabledRowFunc(row)}
              className="min-h-11 min-w-11 bg-transparent"
              aria-label={t('memory.messages.forgetAction')}
              title={t('memory.messages.forgetAction')}
              onClick={() => {
                handleClickDeleteMessage(row.original);
              }}
            >
              <Eraser />
            </Button>
          </div>
        ),
      },
    ],
    [
      handleClickDeleteMessage,
      handleClickMessageContentDialog,
      handleClickUpdateMessageState,
      messageTypeOptions,
      showLog,
    ],
  );

  const currentPagination = useMemo(() => {
    return {
      pageIndex: (pagination.current || 1) - 1,
      pageSize: pagination.pageSize || 10,
    };
  }, [pagination]);
  const [expanded, setExpanded] = React.useState<ExpandedState>({});
  const table = useReactTable({
    data: messages,
    columns,
    onExpandedChange: setExpanded,
    getSubRows: (row) => (row.extract as IMessageInfo[]) || undefined,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    manualPagination: true,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      pagination: currentPagination,
      expanded,
    },
    rowCount: total,
  });

  return (
    <div className="flex w-full flex-col gap-3">
      <div
        className="min-h-[12rem]"
        aria-busy={loading}
        aria-live="polite"
        aria-label={loading ? t('memory.messages.loading') : undefined}
      >
        <Spin spinning={loading} className="min-h-[12rem]">
        <div className="w-full overflow-x-auto">
          <Table rootClassName="max-h-[min(70vh,calc(100vh-20rem))]">
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody className="relative">
              {table.getRowModel().rows?.length ? (
                table.getRowModel().rows.map((row) => (
                  <TableRow
                    key={row.id}
                    data-state={row.getIsSelected() && 'selected'}
                    className={cn('group', {
                      'bg-bg-list/5': !row.getCanExpand(),
                    })}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext(),
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={columns.length}
                    className="h-24 text-center"
                  >
                    {!loading ? <Empty type={EmptyType.Data} /> : null}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </Spin>
      </div>

      {showDeleteDialog && (
        <ConfirmDeleteDialog
          onOk={handleDeleteMessage}
          title={t('memory.messages.forgetMessage')}
          open={showDeleteDialog}
          onOpenChange={setShowDeleteDialog}
          okButtonText={t('memory.messages.forget')}
          content={{
            title: t('memory.messages.forgetMessageTip'),
            node: (
              <ConfirmDeleteDialogNode
                name={
                  t('memory.messages.sessionId') +
                  ': ' +
                  selectedMessage.session_id
                }
                warnText={t('memory.messages.delMessageWarn')}
              />
            ),
          }}
        />
      )}

      {showMessageContentDialog && (
        <Modal
          title={t('memory.messages.content')}
          open={showMessageContentDialog}
          onOpenChange={setShowMessageContentDialog}
          className="w-[min(640px,calc(100vw-2rem))] max-w-[calc(100vw-2rem)]"
          footer={
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowMessageContentDialog(false)}
              >
                {t('common.close')}
              </Button>
            </div>
          }
        >
          <div className="flex flex-col gap-2.5">
            <div className="text-sm text-text-secondary">
              {t('memory.messages.sessionId')}:&nbsp;&nbsp;
              {selectedMessage.session_id}
            </div>
            {selectedMessageContent?.content && (
              <div className="h-fit max-h-[350px] w-full overflow-y-auto whitespace-pre-line text-wrap rounded-lg bg-accent-primary-5 px-2.5 py-1 scrollbar-auto">
                {replaceText(selectedMessageContent?.content || '')}
              </div>
            )}
            {selectedMessageContent?.content_embed && (
              <div className="flex items-center gap-2">
                <CopyToClipboard
                  text={selectedMessageContent?.content_embed}
                  onCopy={() => {
                    setCopied(true);
                    setTimeout(() => setCopied(false), 1000);
                  }}
                >
                  <Button
                    type="button"
                    variant="ghost"
                    className="border border-border-button"
                  >
                    {t('memory.messages.contentEmbed')}
                    <Copy />
                  </Button>
                </CopyToClipboard>
                {copied && (
                  <span className="text-xs text-text-secondary">
                    {t('memory.messages.copied')}
                  </span>
                )}
              </div>
            )}
          </div>
        </Modal>
      )}

      {isModalVisible && (
        <ProcessLogModal
          title={t('memory.taskLogDialog.title')}
          visible={isModalVisible}
          onCancel={() => setIsModalVisible(false)}
          translateKey="memory.taskLogDialog"
          logInfo={logInfo as unknown as ILogInfo}
        />
      )}

      <div className="flex items-center justify-end pt-1">
        <RAGFlowPagination
          {...pick(pagination, 'current', 'pageSize')}
          total={total}
          onChange={(page, pageSize) => {
            setPagination({ page, pageSize });
          }}
        />
      </div>
    </div>
  );
}
