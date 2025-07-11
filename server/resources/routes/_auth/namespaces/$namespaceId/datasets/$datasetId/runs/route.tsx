import { createFileRoute, Outlet } from '@tanstack/react-router'

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/datasets/$datasetId/runs')({
  component: RouteComponent,
})

function RouteComponent() {
  return <Outlet />;
}
