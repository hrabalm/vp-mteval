import { createFileRoute, Link, useNavigate, useRouter } from '@tanstack/react-router';
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, getFilteredRowModel, ColumnFiltersState, SortingState, ColumnDef, ColumnOrderState } from '@tanstack/react-table';
import { addTag, deleteTag, fetchRuns } from '@/runs';
import { Tabs, TabsList, TabsContent, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useMemo, useState } from 'react';
import VirtualizedJSON from '@/components/virtualized-json';
import RefreshBar from '@/components/refresh-bar';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Checkbox } from '@/components/ui/checkbox';
import { isFloat } from '@/lib/utils';
import { Badge } from "@/components/ui/badge";
import { Plus } from "lucide-react"
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from '@/components/ui/label';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import ColumnSelectorDialog from '@/components/column-selector';

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/datasets/$datasetId/runs/')({
  component: RouteComponent,
  loader: ({ params }) => fetchRuns(params.namespaceId, params.datasetId),
})

type Row = Record<string, any>; // unknown shape

function preprocessRunsData(runs: Row[]) {
  return runs.map(run => {
    let processedRun: Row = { ...run };

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
          const safeName = metric.name.replace(/\./g, '․'); // we can't have dots in keys
          const key = `m:${safeName}${metric.higher_is_better ? '↑' : '↓'}`;
          processedRun[key] = metric.score;
        }
      });
      delete processedRun.dataset_metrics;
    }


    return processedRun;
  });
}
function AddTagDialog({ run }: { run: any }) {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const name = formData.get("name");
    await addTag(run.id, run.namespace_name, String(name));
    router.invalidate();
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Plus className="hover:bg-gray-200" />
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={onSubmit}>
          <DialogHeader>
            <DialogTitle>Add a tag</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4">
            <Label htmlFor="name">Tag Name</Label>
            <Input id="name" name="name" placeholder="Add a tag" />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button type="submit">Save changes</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function TagBadge({ run, tag }: { run: any, tag: string }) {
  const router = useRouter();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Badge>
          {tag}
        </Badge>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Actions</DropdownMenuLabel>
        <DropdownMenuItem
          onClick={async () => {
            await deleteTag(run.id, run.namespace_name, tag);
            router.invalidate();
          }}
        >
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function RunsTable({ runs }: { runs: Row[] }) {
  const processedRuns = useMemo(() => preprocessRunsData(runs), [runs]);

  const { namespaceId, datasetId } = Route.useParams();
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnVisibility, setColumnVisibility] = useState({});
  const [columnOrder, setColumnOrder] = useState<ColumnOrderState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [globalFilter, setGlobalFilter] = useState('');

  const [rowSelection, setRowSelection] = useState({});

  const columnHelper = createColumnHelper<Row>();

  const allKeys = useMemo(
    () => Array.from(new Set(processedRuns.flatMap(Object.keys))),
    [processedRuns]
  )

  const regexpFilterFn = (row: any, columnId: string, value: string) => {
    if (!value) return true; // No filter applied, show all rows
    const cellValue = row.getValue(columnId);
    if (cellValue == null) return false;

    const stringifyValue = (s) => {
      if (typeof s === 'object') {
        return JSON.stringify(s);
      }
      return String(s);
    }

    try {
      const regex = new RegExp(value, 'i'); // Case-insensitive regex
      const cellString = stringifyValue(cellValue);
      return regex.test(cellString);
    } catch (error) {
      // Invalid regex, fallback to string includes
      return String(cellValue).toLowerCase().includes(value.toLowerCase());
    }
  };

  const fixedColumns = [
    {
      id: "select",
      header: () => null, // No header for select column
      cell: ({ row }) => (
        <Checkbox checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
        />
      ),
      enableSorting: false,
      enableColumnFilter: false,
      enableHiding: false,
    },
    {
      "id": "id",
      "header": "ID",
      "accessorKey": "id",
      "enableSorting": true,
      "enableColumnFilter": false,
      "enableHiding": false,
      filterFn: regexpFilterFn,
      "cell": (info) => {
        const value = info.getValue();
        return (
          <Link
            to="/namespaces/$namespaceId/datasets/$datasetId/runs/$runId"
            params={{
              namespaceId,
              datasetId,
              runId: info.row.original.id,
            }}
            className="text-blue-500 hover:underline"
          >
            {String(value)}
          </Link>
        );
      },
    },
    {
      "id": "tags",
      "header": "Tags",
      "accessorKey": "tags",
      "enableSorting": true,
      "enableColumnFilter": true,
      "enableHiding": true,
      filterFn: regexpFilterFn,
      "cell": (info) => {
        const tags = info.getValue();
        return (
          <div className="flex flex-wrap gap-1 justify-end">
            {tags.map((tag: string, index: number) => (
              <TagBadge key={index} tag={tag} run={info.row.original} />
            ))}
            <AddTagDialog run={info.row.original} />
          </div>
        );
      }
    }
  ]

  const columns = useMemo<ColumnDef<Row>[]>(
    () =>
      allKeys.filter((key) => !["id", "tags"].includes(key)).map((key) => ({
        accessorKey: key,
        header: key.charAt(0).toUpperCase() + key.slice(1),
        filterFn: regexpFilterFn,
        cell: info => {
          const value = info.getValue();

          // Create links for id and uuid columns
          if ((key === 'uuid') && value) {
            return (
              <Link
                to="/namespaces/$namespaceId/datasets/$datasetId/runs/$runId"
                params={{
                  namespaceId,
                  datasetId,
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

          if ((key !== "id") && (isFloat(value))) {
            return value.toFixed(4);
          }

          return String(value ?? '');
        },
      })),
    [allKeys, namespaceId]
  )

  const table = useReactTable({
    data: processedRuns,
    columns: [
      ...fixedColumns,
      ...columns,
    ],
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onRowSelectionChange: setRowSelection,
    onColumnVisibilityChange: setColumnVisibility,
    onColumnOrderChange: setColumnOrder,
    filterFns: {
      regexp: regexpFilterFn,
    },
    state: {
      sorting,
      columnFilters,
      globalFilter,
      rowSelection,
      columnVisibility,
      columnOrder,
    },
  });

  const runAId = Object.keys(rowSelection)[0];
  const runBId = Object.keys(rowSelection)[1];

  return (
    <div className="space-y-4">
      <div className="flex items-center py-4">
        <Input
          placeholder="Filter runs..."
          value={globalFilter ?? ''}
          onChange={(event: React.ChangeEvent<HTMLInputElement>) => setGlobalFilter(String(event.target.value))}
          className="max-w-sm"
        />
        <Button
          disabled={Object.keys(rowSelection).length !== 2}
        >
          <Link
            to="/namespaces/$namespaceId/datasets/$datasetId/compare"
            params={{
              namespaceId,
              datasetId,
            }}
            search={{
              runAId: processedRuns[runAId]?.id,
              runBId: processedRuns[runBId]?.id,
            }}
          >
            Compare 2
          </Link>
        </Button>
        <ColumnSelectorDialog table={table} />
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup, index) => (
              <TableRow key={`42_${headerGroup.id}_${index}`}>
                {headerGroup.headers.map((header, index) => (
                  <TableHead
                    key={`43_${header.id}_${index}`}
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
                  </TableHead>
                ))}
              </TableRow>
            ))}
            <TableRow key="774">
              {table.getHeaderGroups()[0].headers.map((header, index) => {
                if (header.id !== "select") {
                  return (<TableCell key={`${header.id}_${index}`} className="px-3 py-2">
                    <Input
                      placeholder="Regex..."
                      className="w-full text-xs"
                      value={(header.column.getFilterValue() as string) ?? ''}
                      onChange={(e) => header.column.setFilterValue(e.target.value)}
                    />
                  </TableCell>);
                }
                return <TableCell></TableCell>;
              })}
            </TableRow>
          </TableHeader>
          <TableBody className="bg-background divide-y divide-border">
            {table.getRowModel().rows.map((row, index) => (
              <TableRow key={`${row.id}_${index}`} className="hover:bg-muted/50">
                {row.getVisibleCells().map((cell, index) => (
                  <TableCell key={`${cell.id}_${index}`} className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between space-x-2 py-4">
        <div className="text-sm text-muted-foreground">
          {table.getFilteredRowModel().rows.length} of{' '}
          {table.getCoreRowModel().rows.length} row(s) shown.
          {' '}{table.getSelectedRowModel().rows.length} selected.
        </div>
      </div>
    </div >
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
          >
            <Button>
              Back to Namespace
            </Button>
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
