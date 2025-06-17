import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/datasets/')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/datasets/"!</div>
}
