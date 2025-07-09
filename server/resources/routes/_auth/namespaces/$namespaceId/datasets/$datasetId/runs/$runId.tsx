import { createFileRoute } from '@tanstack/react-router';
import { fetchRun, fetchRunNGrams } from "@/runs";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable, getFilteredRowModel, ColumnFiltersState, PaginationState, getPaginationRowModel } from '@tanstack/react-table';
import { Tabs, TabsList, TabsContent, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { rankItem } from '@tanstack/match-sorter-utils';
import { useState, useCallback, useRef, useMemo } from 'react';
import VirtualizedJSON from '@/components/virtualized-json';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import ColumnSelector from '@/components/column-selector';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Spinner } from '@/components/ui/spinner';

const prettyColumnNames = {
  src: 'Source',
  tgt: 'Target',
  ref: 'Reference',
}

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/datasets/$datasetId/runs/$runId')({
  component: RouteComponent,
  pendingComponent: PendingComponent,
  loader: async ({ params }) => {
    const run = await fetchRun(params.runId, params.namespaceId);
    const n_grams = await fetchRunNGrams(params.runId, params.namespaceId);
    return { run, n_grams };
  },
})

function NGramsRender({ ngrams }: { ngrams: string[] }) {
  return <span>{ngrams.join(' | ')}</span>
}

function ColumnsPopover({ allColumns, selectedColumns, onSelectionChange }) {
  return <Popover>
    <PopoverTrigger asChild><Button variant="outline">Columns</Button></PopoverTrigger>
    <PopoverContent className="w-1/4 flex">
      <ColumnSelector
        allColumns={allColumns}
        selectedColumns={selectedColumns}
        onSelectionChange={onSelectionChange}
      />
    </PopoverContent>
  </Popover >
}

function flattenObject(obj: Record<string, any>): Record<string, any> {
  const result: Record<string, any> = {};
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      if (typeof obj[key] === 'object' && !Array.isArray(obj[key]) && obj[key] !== null) {
        const flatObject = flattenObject(obj[key]);
        for (const flatKey in flatObject) {
          if (flatObject.hasOwnProperty(flatKey)) {
            result[`${key}.${flatKey}`] = flatObject[flatKey];
          }
        }
      } else {
        result[key] = obj[key];
      }
    }
  }
  return result;
}

function OverviewTable({ run, cellFormatters = {}, defaultCellFormatter = (value: any) => <div className="font-medium">{value}</div> }: {
  run: Record<string, any>,
  cellFormatters?: Record<string, (value: any) => React.JSX.Element>,
  defaultCellFormatter?: (value: any) => React.JSX.Element
}) {
  const flat_run = flattenObject(run);
  const data = Object.entries(flat_run).filter(([key, value]) => (
    // if value is an array, return false
    !Array.isArray(value)
  )).map(([key, value]) => ({ key: key, value: value }));
  console.log("DATA: ");
  console.log(JSON.stringify(data, null, 2));
  const columns = ["key", "value"].map(
    key => ({
      accessorKey: key,
      header: () => prettyColumnNames[key] || key,
      cell: ({ row }: { row: any }) => {
        const value = row.getValue(key);
        const formatter = cellFormatters[key] || defaultCellFormatter;
        return formatter(value);
      }
    })
  );

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => {
                return (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                  </TableHead>
                )
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows?.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                data-state={row.getIsSelected() && "selected"}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={columns.length} className="h-24 text-center">
                No results.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}

function RunTable() {
  const { run } = Route.useLoaderData();
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
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })

  const [searchEnabled, setSearchEnabled] = useState(false);
  const [caseSensitiveRE, setCaseSensitiveRE] = useState(true);
  const [selectedColumns, setSelectedColumns] = useState<string[]>(['src', 'tgt', 'ref']);

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
        const flags = (caseSensitiveRE ? '' : 'i');
        const regex = new RegExp(regexpValue, flags);
        matches = matches && regex.test(cellValue);
      } catch (e) {
        // If regexp is invalid, don't filter
        matches = matches && true;
      }
    }

    return matches;
  }, [fuzzyFilters, regexpFilters]);

  const columnHelper = createColumnHelper<any>();

  const columns = useMemo(() => selectedColumns.map(columnId => {
    return columnHelper.accessor(columnId, {
      header: () => prettyColumnNames[columnId] || columnId,
      cell: (info) => {
        if (['tgt_ngrams', 'ref_ngrams'].includes(columnId)) {
          return <NGramsRender ngrams={info.getValue()['1,v1_case'] || []} />;
        }
        return info.getValue();
      },
      filterFn: customFilterFn,
    });
  }), [customFilterFn, selectedColumns]);

  console.log("Segment Metrics: ");
  console.log(JSON.stringify(run.segment_metrics, null, 2));

  const data = useMemo(() => {
    const res = [];
    for (const [segmentIdx, segment] of Object.entries(run.segments)) {
      let x = {
        ...segment,
      };
      for (const [metricName, metric] of Object.entries(run.segment_metrics)) {
        const metricNameSafe = metricName.replace(/\./g, '․'); // we can't have dots in keys
        console.log(`Test ${metricName}`)
        x[`m:${metricNameSafe}`] = metric[segmentIdx].score;
        if (metric[segmentIdx].custom) {
          x[`m:${metricNameSafe}:custom`] = JSON.stringify(metric[segmentIdx].custom, null, 2);
          for (const [key, value] of Object.entries(metric[segmentIdx].custom)) {
            const customKeySafe = key.replace(/\./g, '․'); // we can't have dots in keys
            const formattedValue = typeof value === 'object' ? JSON.stringify(value, null, 2) : value;
            x[`m:${metricNameSafe}:custom:${customKeySafe}`] = formattedValue;
          }
        }
      }
      res.push(x);
    }
    return res;
  }, [run.segments, run.segment_metrics]);

  console.log("Run Data: ", JSON.stringify(data, null, 2));

  const table = useReactTable({
    data,
    columns,
    state: {
      columnFilters,
      pagination,
    },
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onPaginationChange: setPagination,
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
      <Button variant="outline" onClick={() => setSearchEnabled(!searchEnabled)}>
        {searchEnabled ? 'Hide Search' : 'Show Search'}
      </Button>
      <ColumnsPopover
        allColumns={['src', 'tgt', 'ref', ...Object.keys(data[0] || {})]}
        selectedColumns={selectedColumns}
        onSelectionChange={setSelectedColumns}
      />
      <div className={`flex items-center gap-4 ${searchEnabled ? '' : 'collapse'}`}>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={caseSensitiveRE}
            onChange={(e) => setCaseSensitiveRE(e.target.checked)}
            className="rounded border-gray-300"
          />
          Case sensitive regexp
        </label>
      </div>
      <table className="w-full table-fixed divide-y divide-border">
        <thead className="bg-muted/50">
          {table.getHeaderGroups().map(headerGroup => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <th key={header.id} className="w-1/3 px-3 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
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
          <tr className={`bg-muted/20 transition-all duration-200 ${searchEnabled ? '' : 'collapse'}`}>
            <td className="px-3 py-2">
              <Input
                placeholder="Fuzzy search in Source..."
                className="w-full text-xs"
                value={fuzzyFilters.src}
                onChange={(e) => handleFuzzyFilterChange('src', e.target.value)}
              />
            </td>
            <td className="px-3 py-2">
              <Input
                placeholder="Fuzzy search in Target..."
                className="w-full text-xs"
                value={fuzzyFilters.tgt}
                onChange={(e) => handleFuzzyFilterChange('tgt', e.target.value)}
              />
            </td>
            <td className="px-3 py-2">
              <Input
                placeholder="Fuzzy search in Reference..."
                className="w-full text-xs"
                value={fuzzyFilters.ref}
                onChange={(e) => handleFuzzyFilterChange('ref', e.target.value)}
              />
            </td>
          </tr>
          {/* Regexp search row */}
          <tr className={`bg-muted/20 transition-all duration-200 ${searchEnabled ? '' : 'collapse'}`}>
            <td className="px-3 py-2">
              <Input
                placeholder="Regexp search in Source..."
                className="w-full text-xs"
                value={regexpFilters.src}
                onChange={(e) => handleRegexpFilterChange('src', e.target.value)}
              />
            </td>
            <td className="px-3 py-2">
              <Input
                placeholder="Regexp search in Target..."
                className="w-full text-xs"
                value={regexpFilters.tgt}
                onChange={(e) => handleRegexpFilterChange('tgt', e.target.value)}
              />
            </td>
            <td className="px-3 py-2">
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
                <td key={cell.id} className="px-3 py-2 text-sm text-foreground break-words">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Pagination Controls */}
      <div className="flex items-center justify-between px-3 py-4 bg-muted/20 border-t">
        <div className="flex items-center gap-2">
          <button
            className="px-3 py-1 text-xs font-medium border rounded-md bg-background hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => table.firstPage()}
            disabled={!table.getCanPreviousPage()}
          >
            {'<<'}
          </button>
          <button
            className="px-3 py-1 text-xs font-medium border rounded-md bg-background hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            {'<'}
          </button>
          <button
            className="px-3 py-1 text-xs font-medium border rounded-md bg-background hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            {'>'}
          </button>
          <button
            className="px-3 py-1 text-xs font-medium border rounded-md bg-background hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => table.lastPage()}
            disabled={!table.getCanNextPage()}
          >
            {'>>'}
          </button>
        </div>

        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            Page
            <strong className="text-foreground">
              {table.getState().pagination.pageIndex + 1} of{' '}
              {table.getPageCount().toLocaleString()}
            </strong>
          </span>

          <span className="flex items-center gap-2">
            Go to page:
            <input
              type="number"
              min="1"
              max={table.getPageCount()}
              defaultValue={table.getState().pagination.pageIndex + 1}
              onChange={e => {
                const page = e.target.value ? Number(e.target.value) - 1 : 0
                table.setPageIndex(page)
              }}
              className="border rounded-md px-2 py-1 w-16 text-xs bg-background"
            />
          </span>

          <select
            value={table.getState().pagination.pageSize}
            onChange={e => {
              table.setPageSize(Number(e.target.value))
            }}
            className="border rounded-md px-2 py-1 text-xs bg-background"
          >
            {[10, 25, 50, 100, 250, 500, 1000].map(pageSize => (
              <option key={pageSize} value={pageSize}>
                Show {pageSize}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="px-3 py-2 text-xs text-muted-foreground bg-muted/10 border-t">
        Showing {table.getRowModel().rows.length.toLocaleString()} of{' '}
        {table.getRowCount().toLocaleString()} Rows
      </div>
    </div>
  );
}

function NGramsTable({ n, type, data }: { n: number, type: 'confirmed' | 'unconfirmed', data: any[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th className="px-4 py-2">{n}-gram</th>
          <th className="px-4 py-2 text-right">Confirmed - Unconfirmed</th>
        </tr>
      </thead>
      <tbody>
        {data.map((item, index) => (
          <tr key={index}>
            <td className="px-4 py-2">{item.ngrams}</td>
            <td className="px-4 py-2 text-right">{item.confirmed_size} - {item.unconfirmed_size} = {item.confirmed_size - item.unconfirmed_size}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function NGrams({ type }: { type: 'confirmed' | 'unconfirmed' }) {
  const { n_grams } = Route.useLoaderData();
  const selected = type === 'confirmed' ? n_grams.confirmed : n_grams.unconfirmed;
  const n_grams_by_n = selected.reduce((acc: Record<number, any[]>, ngram: any) => {
    const n = ngram.n;
    if (!acc[n]) {
      acc[n] = [];
    }
    acc[n].push(ngram);
    return acc;
  }, {});
  return (
    <div className="rounded-md border p-4">
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="rounded-md border p-4">
          <NGramsTable n={1} type={type} data={n_grams_by_n[1] || []} />
        </div>
        <div className="rounded-md border p-4">
          <NGramsTable n={2} type={type} data={n_grams_by_n[2] || []} />
        </div>
        <div className="rounded-md border p-4">
          <NGramsTable n={3} type={type} data={n_grams_by_n[3] || []} />
        </div>
        <div className="rounded-md border p-4">
          <NGramsTable n={4} type={type} data={n_grams_by_n[4] || []} />
        </div>
      </div>
      <pre className="bg-muted/50 p-4 rounded-md">{JSON.stringify(selected, null, 2)}</pre>
    </div>
  );
}

function PendingComponent() {
  return (
    <div className="flex items-center justify-center h-full">
      <Spinner size="large">Loading run data...</Spinner>
    </div>
  );
}

function RouteComponent() {
  const { run } = Route.useLoaderData();
  console.log(JSON.stringify(run, null, 2));
  return (
    <>
      <h1 className="text-2xl font-bold">Run: {run.id}</h1>
      {/* TODO: add overview of the run */}
      <Tabs defaultValue='segments'>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="segments">Segments</TabsTrigger>
          {run.dataset.has_reference &&
            <>
              <TabsTrigger value="confirmed-ngrams">Confirmed n-grams</TabsTrigger>
              <TabsTrigger value="unconfirmed-ngrams">Unconfirmed n-grams</TabsTrigger>
            </>
          }
          <TabsTrigger value="raw">Raw Data</TabsTrigger>
        </TabsList>
        <TabsContent value="overview"><OverviewTable run={run} /></TabsContent>
        <TabsContent value="segments"><RunTable /></TabsContent>
        {run.dataset.has_reference &&
          <>
            <TabsContent value="confirmed-ngrams">
              <NGrams type="confirmed" />
            </TabsContent>
            <TabsContent value="unconfirmed-ngrams">
              <NGrams type="unconfirmed" />
            </TabsContent>
          </>
        }
        <TabsContent value="raw"><VirtualizedJSON json={run} /></TabsContent>
      </Tabs>
    </>
  );
}
