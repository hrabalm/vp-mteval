import { createFileRoute } from '@tanstack/react-router';
import { fetchRun } from "../../../runs";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';

export const Route = createFileRoute('/_auth/runs/$runId')({
  component: RouteComponent,
  loader: ({ params: { runId } }) => fetchRun(runId),
})

function RouteComponent() {
  const { runId } = Route.useParams();
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
    <>
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
      <pre className="mt-4">{JSON.stringify(run, null, 4)}</pre>
    </>
  );
}

