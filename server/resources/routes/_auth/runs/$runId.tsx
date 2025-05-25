import { createFileRoute } from '@tanstack/react-router';
import { fetchRun } from "../../../runs";

export const Route = createFileRoute('/_auth/runs/$runId')({
  component: RouteComponent,
  loader: ({ params: { runId } }) => fetchRun(runId),
})

function RouteComponent() {
  const { runId } = Route.useParams();

  const run = Route.useLoaderData();

  return <>
    <div>Hello `/runs/{runId}`!</div>
    <pre>{JSON.stringify(run)}</pre>
  </>;
}
