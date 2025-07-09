import { createFileRoute, Link } from '@tanstack/react-router'
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, getFilteredRowModel, ColumnFiltersState, SortingState, ColumnDef } from '@tanstack/react-table';
import { fetchNamespaces } from '../../../namespaces';
import { Input } from '@/components/ui/input';
import { useMemo, useState } from 'react';

type Namespace = {
  id: string;
  name: string;
};

export const Route = createFileRoute('/_auth/namespaces/')({
  component: RouteComponent,
  loader: () => fetchNamespaces(),
})

function NamespacesTable({ namespaces }: { namespaces: Namespace[] }) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [globalFilter, setGlobalFilter] = useState('');

  const columnHelper = createColumnHelper<Namespace>();

  const columns = useMemo<ColumnDef<Namespace, any>[]>(() => [
    {
      accessorKey: 'id',
      header: 'ID',
      cell: info => info.getValue(),
    },
    {
      accessorKey: 'name',
      header: 'Name',
      cell: info => (
        <Link
          to="/namespaces/$namespaceId"
          params={{ namespaceId: String(info.getValue()) }}
          className="text-blue-500 hover:underline"
        >{String(info.getValue())}</Link>
      ),
    },
  ], []);

  const table = useReactTable({
    data: namespaces,
    columns: columns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    state: {
      sorting,
      columnFilters,
      globalFilter,
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center py-4">
        <Input
          placeholder="Filter namespaces..."
          value={globalFilter ?? ''}
          onChange={(event: React.ChangeEvent<HTMLInputElement>) => setGlobalFilter(String(event.target.value))}
          className="max-w-sm"
        />
      </div>
      <div className="rounded-md border">
        <table className="min-w-full divide-y divide-border">
          <thead className="bg-muted/50">
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => (
                  <th
                    key={header.id}
                    className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer select-none"
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center space-x-1">
                      <span>
                        {header.isPlaceholder
                          ? null
                          : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                      </span>
                      {{
                        asc: ' ▲',
                        desc: ' ▼',
                      }[header.column.getIsSorted() as string] ?? null}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-background divide-y divide-border">
            {table.getRowModel().rows.map(row => (
              <tr key={row.id} className="hover:bg-muted/50">
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between space-x-2 py-4">
        <div className="text-sm text-muted-foreground">
          {table.getFilteredRowModel().rows.length} of{' '}
          {table.getCoreRowModel().rows.length} row(s) shown.
        </div>
      </div>
    </div>
  );
}

function RouteComponent() {
  const namespaces = Route.useLoaderData();

  return (
    <div>
      <h1>Namespaces</h1>
      <NamespacesTable namespaces={namespaces} />
    </div>
  );
}
