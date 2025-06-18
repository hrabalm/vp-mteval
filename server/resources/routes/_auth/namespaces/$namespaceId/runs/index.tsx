import { createFileRoute, Link } from '@tanstack/react-router';
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, getFilteredRowModel, ColumnFiltersState, SortingState } from '@tanstack/react-table';
import { fetchRuns } from '../../../../../runs';
import { Tabs, TabsList, TabsContent, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useState } from 'react';

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/runs/')({
  component: RouteComponent,
  loader: ({ params }) => fetchRuns(params.namespaceId),
})

// Define a type for a run row
interface RunRow {
  id: string;
  uuid: string;
  dataset_id: string;
  namespace_id: string;
  namespace_name: string;
  config: string;
  [key: string]: any;
}


function RunsTable({ runs }: { runs: RunRow[] }) {
  const namespaceId = Route.useParams().namespaceId;
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [globalFilter, setGlobalFilter] = useState('');

  const columnHelper = createColumnHelper<RunRow>();

  const columns = [
    columnHelper.accessor('id', {
      header: 'ID',
      cell: ({ getValue }) => (
        <Link
          to="/namespaces/$namespaceId/runs/$runId"
          params={{ namespaceId: namespaceId, runId: getValue() }}
          className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline"
        >
          {getValue()}
        </Link>
      ),
    }),
    columnHelper.accessor('uuid', {
      header: 'UUID',
    }),
    columnHelper.accessor('dataset_id', {
      header: 'Dataset ID',
    }),
    columnHelper.accessor('namespace_id', {
      header: 'Namespace ID',
    }),
    columnHelper.accessor('namespace_name', {
      header: 'Namespace Name',
    }),
    columnHelper.accessor('config', {
      header: 'Config',
    }),
  ];

  const table = useReactTable({
    data: runs,
    columns,
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
          placeholder="Filter runs..."
          value={globalFilter ?? ''}
          onChange={(event: React.ChangeEvent<HTMLInputElement>) => setGlobalFilter(String(event.target.value))}
          className="max-w-sm"
        />
      </div>
      <div className="rounded-md border">
        <table className="min-w-full divide-y divide-border">
          <thead className="bg-muted/50">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
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
                        asc: ' 🔼',
                        desc: ' 🔽',
                      }[header.column.getIsSorted() as string] ?? null}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-background divide-y divide-border">
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="hover:bg-muted/50">
                {row.getVisibleCells().map((cell) => (
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
  const runs = Route.useLoaderData();
  const { namespaceId } = Route.useParams();

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Runs for Namespace: {namespaceId}</h1>
        <Link
          to="/namespaces/$namespaceId"
          params={{ namespaceId }}
          className="px-3 py-2 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 rounded-md"
        >
          Back to Namespace
        </Link>
      </div>

      <Tabs defaultValue='list'>
        <TabsList>
          <TabsTrigger value="list">List</TabsTrigger>
          <TabsTrigger value="raw">Raw Data</TabsTrigger>
        </TabsList>
        <TabsContent value="list"><RunsTable runs={runs} /></TabsContent>
        <TabsContent value="raw"><pre className="mt-2 p-2 bg-slate-100 dark:bg-slate-900 rounded overflow-auto">{JSON.stringify(runs, null, 2)}</pre></TabsContent>
      </Tabs>
    </div>
  );
}
