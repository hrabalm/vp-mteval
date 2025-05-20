import { createRootRoute, Link, Outlet } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'

export const Route = createRootRoute({
  component: () => (
    <>
      <div className="p-2 flex gap-2">
        <Link to="/" className="[&.active]:font-bold">
          Home
        </Link>{' '}
        <Link to="/namespaces/" className='[&.active]:font-bold'>
          Namespaces
        </Link>
        <Link to="/datasets/" className='[&.active]:font-bold'>
          Datasets
        </Link>
        <Link to="/runs" className='[&.active]:font-bold'>
          Runs
        </Link>
        <Link to="/settings" className="[&.active]:font-bold">
          Settings
        </Link>
      </div>
      <hr />
      <Outlet />
      <TanStackRouterDevtools />
    </>
  ),
})
