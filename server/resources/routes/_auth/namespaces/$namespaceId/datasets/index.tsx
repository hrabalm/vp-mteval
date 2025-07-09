import VirtualizedJSON from '@/components/virtualized-json';
import { fetchDatasets } from '@/datasets'
import { createFileRoute, Link } from '@tanstack/react-router'
import { Tabs, TabsList, TabsContent, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable, getFilteredRowModel, ColumnFiltersState, PaginationState, getPaginationRowModel } from '@tanstack/react-table';

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/datasets/')({
  component: RouteComponent,
  loader: ({ params }) => fetchDatasets(params.namespaceId),
})

function DatasetsTable({ }) {
  const datasets = Route.useLoaderData();
  const namespaceId = Route.useParams().namespaceId;
  const columns = [
    {
      accessorKey: "id",
      header: () => "ID",
    },
    {
      accessorKey: "names",
      header: () => "Names",
      cell: info => {
        const value = info.getValue();
        const datasetId = info.row.original.id;

        return (
          <>
            <Link
              to="/namespaces/$namespaceId/datasets/$datasetId"
              params={{ namespaceId: namespaceId, datasetId: datasetId }}
              className="text-blue-500 hover:underline"
            >{value.join(" | ")}</Link>
          </>
        )
      }
    },
    {
      accessorKey: "source_lang",
      header: () => "Source Language",
    },
    {
      accessorKey: "target_lang",
      header: () => "Target Language",
    },
  ]
  const table = useReactTable({
    data: datasets,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })
  return <>
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
  </>
}

function RouteComponent() {
  const datasets = Route.useLoaderData();
  console.log('Datasets:', datasets);
  // return
  return <>
    <Tabs defaultValue='list'>
      <TabsList>
        <TabsTrigger value="list">List</TabsTrigger>
        <TabsTrigger value="raw">Raw Data</TabsTrigger>
      </TabsList>
      <TabsContent value="list">
        <DatasetsTable />
      </TabsContent>
      <TabsContent value="raw"><VirtualizedJSON json={datasets} /></TabsContent>
    </Tabs>
  </>
}
