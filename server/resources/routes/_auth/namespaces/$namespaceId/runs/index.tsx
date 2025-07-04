import { createFileRoute, Link, useRouter } from '@tanstack/react-router';
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, getFilteredRowModel, ColumnFiltersState, SortingState, ColumnDef } from '@tanstack/react-table';
import { fetchRuns } from '../../../../../runs';
import { Tabs, TabsList, TabsContent, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useMemo, useState } from 'react';
import VirtualizedJSON from '@/components/virtualized-json';
import RefreshBar from '@/components/refresh-bar';

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/runs/')({
  component: RouteComponent,
  loader: ({ params }) => fetchRuns(params.namespaceId),
})

type Row = Record<string, any>; // unknown shape

function preprocessRunsData(runs: Row[]) {
  return runs.map(run => {
    let processedRun: Row = { ...run };

    // Delete namespace_name - it is not relevant here
    delete processedRun.namespace_name;

    // Run contains config object, flatten it to c:[element]
    if (run.config && typeof run.config === 'object') {
      Object.entries(run.config).forEach(([key, value]) => {
        processedRun[`c:${key}`] = value;
      });
      delete processedRun.config;
    }

    // Run contains a list of dataset level metrics, flatten them to m:[element][↑ | ↓] (only the score is shown)
    /* Example:
    "dataset_metrics": [
      {
        "name": "BLEU",
        "score": 100.00000000000004,
        "higher_is_better": true,
        "run_id": 178
      }
    ]
    */

    if (run.dataset_metrics && Array.isArray(run.dataset_metrics)) {
      run.dataset_metrics.forEach((metric, index) => {
        if (metric.name && metric.score !== undefined) {
          const key = `m:${metric.name}${metric.higher_is_better ? '↑' : '↓'}`;
          processedRun[key] = metric.score;
        }
      });
      delete processedRun.dataset_metrics;
    }


    return processedRun;
  });
}

function RunsTable({ runs }: { runs: Row[] }) {
  const processedRuns = useMemo(() => preprocessRunsData(runs), [runs]);
  console.log('Processed Runs:', processedRuns);

  const namespaceId = Route.useParams().namespaceId;
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [globalFilter, setGlobalFilter] = useState('');

  const columnHelper = createColumnHelper<Row>();

  const allKeys = useMemo(
    () => Array.from(new Set(processedRuns.flatMap(Object.keys))),
    [processedRuns]
  )

  const regexpFilterFn = (row: any, columnId: string, value: string) => {
    if (!value) return true; // No filter applied, show all rows
    const cellValue = row.getValue(columnId);
    if (cellValue == null) return false;

    try {
      const regex = new RegExp(value, 'i'); // Case-insensitive regex
      // return regex.test(String(cellValue));
      return regex.test(JSON.stringify(cellValue));  // FIXME
    } catch (error) {
      // Invalid regex, fallback to string includes
      return String(cellValue).toLowerCase().includes(value.toLowerCase());
    }
  };

  const columns = useMemo<ColumnDef<Row>[]>(
    () =>
      allKeys.map((key) => ({
        accessorKey: key,
        header: key.charAt(0).toUpperCase() + key.slice(1),
        filterFn: regexpFilterFn,
        cell: info => {
          const value = info.getValue();

          // Create links for id and uuid columns
          if ((key === 'id' || key === 'uuid') && value) {
            return (
              <Link
                to="/namespaces/$namespaceId/runs/$runId"
                params={{
                  namespaceId,
                  runId: info.row.original.id,
                }}
                className="text-blue-500 hover:underline"
              >
                {String(value)}
              </Link>
            );
          } else if ((key === 'dataset') && value) {
            // FIXME: should be flattened instead
            return value.names;
          }

          return String(value ?? '');
        },
      })),
    [allKeys, namespaceId]
  )

  const table = useReactTable({
    data: processedRuns,
    columns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    filterFns: {
      regexp: regexpFilterFn,
    },
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
                        asc: ' ▲',
                        desc: ' ▼',
                      }[header.column.getIsSorted() as string] ?? null}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
            <tr>
              {table.getHeaderGroups()[0].headers.map((header) => (
                <td key={header.id} className="px-3 py-2">
                  <Input
                    placeholder="Regex..."
                    className="w-full text-xs"
                    value={(header.column.getFilterValue() as string) ?? ''}
                    onChange={(e) => header.column.setFilterValue(e.target.value)}
                  />
                </td>))}
            </tr>
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
  const router = useRouter();
  const runs = Route.useLoaderData();
  const { namespaceId } = Route.useParams();

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Runs for Namespace: {namespaceId}</h1>
        <div className="flex space-x-4">

          <RefreshBar onRefresh={() => router.invalidate()} isRefreshing={false} />
          <Link
            to="/namespaces/$namespaceId"
            params={{ namespaceId }}
            className="px-3 py-2 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 rounded-md"
          >
            Back to Namespace
          </Link>
        </div>
      </div>

      <Tabs defaultValue='list'>
        <TabsList>
          <TabsTrigger value="list">List</TabsTrigger>
          <TabsTrigger value="raw">Raw Data</TabsTrigger>
        </TabsList>
        <TabsContent value="list"><RunsTable runs={runs} /></TabsContent>
        <TabsContent value="raw"><VirtualizedJSON json={runs} /></TabsContent>
      </Tabs>
    </div>
  );
}
