import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_auth/datasets/$datasetId')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/datasets/$datasetId"!</div>
}
