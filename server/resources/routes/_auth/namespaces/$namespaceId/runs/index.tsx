import { createFileRoute, Link } from '@tanstack/react-router';
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { fetchRuns } from '../../../../../runs';

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/runs/')({
  component: RouteComponent,
  loader: ({ params }) => fetchRuns(params.namespaceId),
})

function RunsTable({ runs }) {
  const columnHelper = createColumnHelper();
  const namespaceId = Route.useParams().namespaceId;

  // TODO: columns are dynamic and have to be configurable (based on available settings and metrics)
  const columns = [
    columnHelper.accessor('id', {
      header: () => 'ID',
      cell: ({ getValue }) => (
        <Link
          to="/namespaces/$namespaceId/runs/$runId"
          params={{ namespaceId: namespaceId, runId: getValue() }}
          className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline"
        >{getValue()}</Link>
      ),
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
                <th key={header.id} className="border border-gray-300 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-4 py-2 text-left font-semibold">
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
            <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} className="border border-gray-300 dark:border-gray-700 px-4 py-2">
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
      
      <RunsTable runs={runs} />
      
      {/* Optional: Show raw data in expandable section */}
      <details className="mt-8 bg-white dark:bg-slate-800 p-4 rounded-lg">
        <summary className="cursor-pointer font-medium">Raw Data</summary>
        <pre className="mt-2 p-2 bg-slate-100 dark:bg-slate-900 rounded overflow-auto">{JSON.stringify(runs, null, 2)}</pre>
      </details>
    </div>
  );
}
