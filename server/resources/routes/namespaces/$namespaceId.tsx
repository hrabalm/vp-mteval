import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/namespaces/$namespaceId')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/namespaces/$namespaceId"!</div>
}
