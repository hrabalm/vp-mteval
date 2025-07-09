import { createFileRoute, Outlet } from '@tanstack/react-router'

export const Route = createFileRoute('/_auth/namespaces')({
  component: RouteComponent,
})

function RouteComponent() {
  return <Outlet />;
}
