import { ModeToggle } from '@/components/mode-toggle'
import { createRootRoute, Link, Outlet } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'

const appName = import.meta.env.VITE_APP_NAME || 'VP MTEval'

const NavLink = ({ to, children }: { to: string, children: React.ReactNode }) => (
  <Link
    to={to}
    className="flex items-center px-4 py-2 text-slate-700 dark:text-slate-300 rounded-md hover:bg-slate-200 dark:hover:bg-slate-700 [&.active]:bg-slate-200 dark:[&.active]:bg-slate-700 [&.active]:font-medium [&.active]:text-slate-900 dark:[&.active]:text-slate-100"
  >
    {children}
  </Link>
)

export const Route = createRootRoute({
  component: () => (
    <div className="flex h-screen dark:bg-slate-900">
      {/* Sidebar */}
      <div className="w-64 bg-slate-50 dark:bg-slate-800 border-r border-slate-200 dark:border-slate-700 h-full flex flex-col">
        <div className="p-4 border-b border-slate-200 dark:border-slate-700">
          <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">{appName}</h1>
          <ModeToggle />
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <NavLink to="/">Home</NavLink>
          <NavLink to="/namespaces">Namespaces</NavLink>
          <NavLink to="/datasets">Datasets</NavLink>
          <NavLink to="/runs">Runs</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden dark:bg-slate-900">
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
        <TanStackRouterDevtools />
      </div>
    </div>
  ),
})
