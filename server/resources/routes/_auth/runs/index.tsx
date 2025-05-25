import { createFileRoute } from '@tanstack/react-router';
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { fetchRuns } from '../../../runs';

export const Route = createFileRoute('/_auth/runs/')({
  component: RouteComponent,
  loader: () => fetchRuns(),
})

function RunsTable({ runs }) {
  const columnHelper = createColumnHelper();

  // TODO: columns are dynamic and have to be configurable (based on available settings and metrics)
  const columns = [
    columnHelper.accessor('id', {
      header: () => 'ID',
    }),
    columnHelper.accessor('uuid', {
      header: () => 'UUID',
    }),
    columnHelper.accessor('dataset_id', {
      header: () => 'Dataset ID',
    }),
    columnHelper.accessor('namespace_id', {
      header: () => 'Namespace ID',
    }),
    columnHelper.accessor('namespace_name', {
      header: () => 'Namespace Name',
    }),
    columnHelper.accessor('config', {
      header: () => 'Config',
    }),
  ]

  const table = useReactTable({
    data: runs,
    columns: columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse">
        <thead>
          {table.getHeaderGroups().map(headerGroup => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <th key={header.id} className="border border-gray-300 bg-gray-100 px-4 py-2 text-left font-semibold">
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
        <tbody>
          {table.getRowModel().rows.map(row => (
            <tr key={row.id} className="hover:bg-gray-50">
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} className="border border-gray-300 px-4 py-2">
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
  const runs = Route.useLoaderData();

  return (
    <div>
      <h1>Runs</h1>
      <RunsTable runs={runs} />
      <pre>{JSON.stringify(runs, null, 2)}</pre>
    </div>
  );
}
