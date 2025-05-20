import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/runs/$runId')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/runs/$runId"!</div>
}
