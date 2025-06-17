import { createFileRoute, useRouter } from '@tanstack/react-router'
import { useAuth } from '../auth'

export const Route = createFileRoute('/logout')({
  component: RouteComponent,
})

function RouteComponent() {
  const auth = useAuth()
  const router = useRouter()
  auth.logout()
  router.navigate({ to: '/' })

  return <div>Redirecting...</div>
}
