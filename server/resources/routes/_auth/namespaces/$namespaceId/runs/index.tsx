import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { fetchRuns } from '../../../../../runs';
import { Tabs, TabsList, TabsContent, TabsTrigger } from '@/components/ui/tabs';
import DataTable from 'datatables.net-react';
import DT from 'datatables.net-dt';
import 'datatables.net-responsive-dt';
import 'datatables.net-select-dt';
import 'datatables.net-columncontrol-dt';
import { useRef, useEffect } from 'react';

DataTable.use(DT);

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/runs/')({
  component: RouteComponent,
  loader: ({ params }) => fetchRuns(params.namespaceId),
})

// Define a type for a run row
interface RunRow {
  id: string;
  uuid: string;
  dataset_id: string;
  namespace_id: string;
  namespace_name: string;
  config: string;
  [key: string]: any;
}

function RunsTable({ runs }: { runs: RunRow[] }) {
  const namespaceId = Route.useParams().namespaceId;
  const navigate = useNavigate();
  const tableRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Handle click events for navigation
  useEffect(() => {
    const handleClick = (e: Event) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'A' && target.hasAttribute('data-run-id')) {
        e.preventDefault();
        const runId = target.getAttribute('data-run-id');
        if (runId) {
          // Use TanStack Router's navigate for client-side navigation
          navigate({
            to: '/namespaces/$namespaceId/runs/$runId',
            params: { namespaceId, runId }
          });
        }
      }
    };

    const container = containerRef.current;
    if (container) {
      container.addEventListener('click', handleClick);
      return () => container.removeEventListener('click', handleClick);
    }
  }, [namespaceId, navigate]);

  // Define columns for DataTables
  const columns = [
    {
      title: 'ID',
      data: 'id',
      render: function (data: string, type: string, row: RunRow) {
        if (type === 'display') {
          return `<a href="/namespaces/${namespaceId}/runs/${data}" class="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline cursor-pointer" data-run-id="${data}">${data}</a>`;
        }
        return data;
      },
    },
    { title: 'UUID', data: 'uuid' },
    { title: 'Dataset ID', data: 'dataset_id' },
    { title: 'Namespace ID', data: 'namespace_id' },
    { title: 'Namespace Name', data: 'namespace_name' },
    { title: 'Config', data: 'config' },
  ];

  return (
    <div className="overflow-x-auto" ref={containerRef}>
      <DataTable
        ref={tableRef}
        data={runs}
        columns={columns}
        className="display nowrap min-w-full"
        options={{
          responsive: true,
          select: true,
          paging: true,
          searching: true,
          info: true,
          autoWidth: false,
          destroy: true, // Allow reinitialization
        }}
      />
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

      <Tabs defaultValue='list'>
        <TabsList>
          <TabsTrigger value="list">List</TabsTrigger>
          <TabsTrigger value="raw">Raw Data</TabsTrigger>
        </TabsList>
        <TabsContent value="list"><RunsTable runs={runs} /></TabsContent>
        <TabsContent value="raw"><pre className="mt-2 p-2 bg-slate-100 dark:bg-slate-900 rounded overflow-auto">{JSON.stringify(runs, null, 2)}</pre></TabsContent>
      </Tabs>
    </div>
  );
}
