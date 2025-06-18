import { createFileRoute } from '@tanstack/react-router';
import { fetchRun } from "../../../../../runs";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { Tabs, TabsList, TabsContent, TabsTrigger } from '@/components/ui/tabs';

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/runs/$runId')({
  component: RouteComponent,
  loader: ({ params }) => fetchRun(params.runId, params.namespaceId),
})

function RunTable() {
  const run = Route.useLoaderData();

  const columnHelper = createColumnHelper();

  const columns = [
    columnHelper.accessor('src', {
      header: () => 'Source',
      cell: info => info.getValue(),
    }),
    columnHelper.accessor('tgt', {
      header: () => 'Target',
      cell: info => info.getValue(),
    }),
    columnHelper.accessor('ref', {
      header: () => 'Reference',
      cell: info => info.getValue() ?? 'N/A',
    }),
  ];

  const table = useReactTable({
    data: run.segments,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

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

