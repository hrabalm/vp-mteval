import { createFileRoute } from '@tanstack/react-router';
import { fetchRun } from "../../../../../runs";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable, getFilteredRowModel, ColumnFiltersState } from '@tanstack/react-table';
import { Tabs, TabsList, TabsContent, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { rankItem } from '@tanstack/match-sorter-utils';
import { useState, useCallback, useRef, useMemo } from 'react';

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/runs/$runId')({
  component: RouteComponent,
  loader: ({ params }) => fetchRun(params.runId, params.namespaceId),
})

function RunTable() {
  const run = Route.useLoaderData();
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [fuzzyFilters, setFuzzyFilters] = useState({
    src: '',
    tgt: '',
    ref: ''
  });
  const [regexpFilters, setRegexpFilters] = useState({
    src: '',
    tgt: '',
    ref: ''
  });

  // Refs for debouncing
  const fuzzyTimeoutRefs = useRef<{ [key: string]: NodeJS.Timeout }>({});
  const regexpTimeoutRefs = useRef<{ [key: string]: NodeJS.Timeout }>({});

  // Debounced filter update function
  const updateTableFilters = useCallback((columnId: string) => {
    setColumnFilters(prev => {
      const existing = prev.find(filter => filter.id === columnId);
      if (existing) {
        return prev.map(filter =>
          filter.id === columnId ? { ...filter, value: Date.now() } : filter
        );
      } else {
        return [...prev, { id: columnId, value: Date.now() }];
      }
    });
  }, []);

  // Custom filter function for fuzzy and regexp search
  const customFilterFn = useCallback((row: any, columnId: string, value: any) => {
    const cellValue = row.getValue(columnId) || '';
    const fuzzyValue = fuzzyFilters[columnId as keyof typeof fuzzyFilters];
    const regexpValue = regexpFilters[columnId as keyof typeof regexpFilters];

    let matches = true;

    // Apply fuzzy filter if present
    if (fuzzyValue) {
      const ranked = rankItem(cellValue, fuzzyValue);
      matches = matches && ranked.passed;
    }

    // Apply regexp filter if present
    if (regexpValue) {
      try {
        const regex = new RegExp(regexpValue, 'i');
        matches = matches && regex.test(cellValue);
      } catch (e) {
        // If regexp is invalid, don't filter
        matches = matches && true;
      }
    }

    return matches;
  }, [fuzzyFilters, regexpFilters]);

  const columnHelper = createColumnHelper<any>();

  const columns = useMemo(() => [
    columnHelper.accessor('src', {
      header: () => 'Source',
      cell: info => info.getValue(),
      filterFn: customFilterFn,
    }),
    columnHelper.accessor('tgt', {
      header: () => 'Target',
      cell: info => info.getValue(),
      filterFn: customFilterFn,
    }),
    columnHelper.accessor('ref', {
      header: () => 'Reference',
      cell: info => info.getValue() ?? 'N/A',
      filterFn: customFilterFn,
    }),
  ], [customFilterFn]);

  const table = useReactTable({
    data: run.segments,
    columns,
    state: {
      columnFilters,
    },
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const handleFuzzyFilterChange = useCallback((columnId: string, value: string) => {
    setFuzzyFilters(prev => ({ ...prev, [columnId]: value }));

    // Clear existing timeout for this column
    if (fuzzyTimeoutRefs.current[columnId]) {
      clearTimeout(fuzzyTimeoutRefs.current[columnId]);
    }

    // Set new timeout for debounced update
    fuzzyTimeoutRefs.current[columnId] = setTimeout(() => {
      updateTableFilters(columnId);
    }, 10);
  }, [updateTableFilters]);

  const handleRegexpFilterChange = useCallback((columnId: string, value: string) => {
    setRegexpFilters(prev => ({ ...prev, [columnId]: value }));

    // Clear existing timeout for this column
    if (regexpTimeoutRefs.current[columnId]) {
      clearTimeout(regexpTimeoutRefs.current[columnId]);
    }

    // Set new timeout for debounced update
    regexpTimeoutRefs.current[columnId] = setTimeout(() => {
      updateTableFilters(columnId);
    }, 10);
  }, [updateTableFilters]);

  return (
    <div className="rounded-md border">
      <table className="w-full table-fixed divide-y divide-border">
        <thead className="bg-muted/50">
          {table.getHeaderGroups().map(headerGroup => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <th key={header.id} className="w-1/3 px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                      header.column.columnDef.header,
                      header.getContext()
                    )}
                </th>
              ))}
            </tr>
          ))}
          {/* Fuzzy search row */}
          <tr className="bg-muted/20">
            <td className="px-6 py-2">
              <Input
                placeholder="Fuzzy search in Source..."
                className="w-full text-xs"
                value={fuzzyFilters.src}
                onChange={(e) => handleFuzzyFilterChange('src', e.target.value)}
              />
            </td>
            <td className="px-6 py-2">
              <Input
                placeholder="Fuzzy search in Target..."
                className="w-full text-xs"
                value={fuzzyFilters.tgt}
                onChange={(e) => handleFuzzyFilterChange('tgt', e.target.value)}
              />
            </td>
            <td className="px-6 py-2">
              <Input
                placeholder="Fuzzy search in Reference..."
                className="w-full text-xs"
                value={fuzzyFilters.ref}
                onChange={(e) => handleFuzzyFilterChange('ref', e.target.value)}
              />
            </td>
          </tr>
          {/* Regexp search row */}
          <tr className="bg-muted/10">
            <td className="px-6 py-2">
              <Input
                placeholder="Regexp search in Source..."
                className="w-full text-xs"
                value={regexpFilters.src}
                onChange={(e) => handleRegexpFilterChange('src', e.target.value)}
              />
            </td>
            <td className="px-6 py-2">
              <Input
                placeholder="Regexp search in Target..."
                className="w-full text-xs"
                value={regexpFilters.tgt}
                onChange={(e) => handleRegexpFilterChange('tgt', e.target.value)}
              />
            </td>
            <td className="px-6 py-2">
              <Input
                placeholder="Regexp search in Reference..."
                className="w-full text-xs"
                value={regexpFilters.ref}
                onChange={(e) => handleRegexpFilterChange('ref', e.target.value)}
              />
            </td>
          </tr>
        </thead>
        <tbody className="bg-background divide-y divide-border">
          {table.getRowModel().rows.map(row => (
            <tr key={row.id} className="hover:bg-muted/50">
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} className="px-6 py-4 text-sm text-foreground break-words">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RouteComponent() {
  const run = Route.useLoaderData();
  return (
    <>
      <h1 className="text-2xl font-bold">Run: {run.id}</h1>
      {/* TODO: add overview of the run */}
      <Tabs defaultValue='segments'>
        <TabsList>
          <TabsTrigger value="segments">Segments</TabsTrigger>
          <TabsTrigger value="raw">Raw Data</TabsTrigger>
        </TabsList>
        <TabsContent value="segments"><RunTable /></TabsContent>
        <TabsContent value="raw"><pre className="mt-4">{JSON.stringify(run, null, 4)}</pre></TabsContent>
      </Tabs>
    </>
  );
}

