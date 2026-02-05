import { useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table';
import { useState } from 'react';
import type { Trade } from '../types';

interface Props {
  trades: Trade[];
}

const columnHelper = createColumnHelper<Trade>();

function formatTime(ts: string): string {
  if (!ts) return '-';
  const d = new Date(ts);
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export default function TradeHistory({ trades }: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState('');

  const columns = useMemo(
    () => [
      columnHelper.accessor('side', {
        header: 'Side',
        cell: (info) => (
          <span className={info.getValue().toUpperCase() === 'BUY' ? 'text-green' : 'text-red'}>
            {info.getValue().toUpperCase()}
          </span>
        ),
      }),
      columnHelper.accessor('symbol', {
        header: 'Symbol',
      }),
      columnHelper.accessor('entry_time', {
        header: 'Entry Time',
        cell: (info) => formatTime(info.getValue()),
      }),
      columnHelper.accessor('exit_time', {
        header: 'Exit Time',
        cell: (info) => formatTime(info.getValue()),
      }),
      columnHelper.accessor('entry_price', {
        header: 'Entry',
        cell: (info) => <span className="mono">{info.getValue().toFixed(5)}</span>,
      }),
      columnHelper.accessor('exit_price', {
        header: 'Exit',
        cell: (info) => <span className="mono">{info.getValue().toFixed(5)}</span>,
      }),
      columnHelper.accessor('volume', {
        header: 'Volume',
        cell: (info) => <span className="mono">{info.getValue().toFixed(2)}</span>,
      }),
      columnHelper.accessor('pnl', {
        header: 'P&L',
        cell: (info) => {
          const val = info.getValue();
          return (
            <span className="mono" style={{ color: val >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {val >= 0 ? '+' : ''}
              {val.toFixed(2)}
            </span>
          );
        },
      }),
      columnHelper.accessor('exit_reason', {
        header: 'Exit Reason',
        cell: (info) => info.getValue() || '-',
      }),
    ],
    []
  );

  const table = useReactTable({
    data: trades,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  return (
    <div className="card trade-history">
      <div className="card-header">
        <h2 className="card-title">Trade History</h2>
        <input
          type="text"
          placeholder="Filter trades..."
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="filter-input"
        />
      </div>
      <div className="table-wrapper">
        <table>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    onClick={header.column.getToggleSortingHandler()}
                    style={{ cursor: header.column.getCanSort() ? 'pointer' : 'default' }}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    {{ asc: ' \u25B2', desc: ' \u25BC' }[header.column.getIsSorted() as string] ?? ''}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="empty-row">
                  No trade history
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
