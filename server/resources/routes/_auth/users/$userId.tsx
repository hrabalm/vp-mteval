import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_auth/users/$userId')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/_auth/users/$userId"!</div>
}
