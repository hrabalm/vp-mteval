import { createFileRoute, Link } from '@tanstack/react-router'
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { fetchNamespaces } from '../../../namespaces';

export const Route = createFileRoute('/_auth/namespaces/')({
  component: RouteComponent,
  loader: () => fetchNamespaces(),
})

function NamespacesTable({ namespaces }) {
  const columnHelper = createColumnHelper();

  const columns = [
    columnHelper.accessor('id', {
      header: () => 'ID',
      cell: ({ getValue }) => getValue(),
    }),
    columnHelper.accessor('name', {
      header: () => 'Name',
      cell: ({ getValue }) => (
        <Link
          to="/namespaces/$namespaceId/runs"
          params={{ namespaceId: getValue() }}
          className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline"
        >{getValue()}</Link>
      ),
    }),
  ]

  const table = useReactTable({
    data: namespaces,
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
  const namespaces = Route.useLoaderData();

  return (
    <div>
      <h1>Namespaces</h1>
      <NamespacesTable namespaces={namespaces} />
    </div>
  );
}
