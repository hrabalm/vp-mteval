import { ModeToggle } from '@/components/mode-toggle'
import { createRootRoute, Link, Outlet, useMatches } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { useState } from 'react'

const appName = import.meta.env.VITE_APP_NAME || 'VP MTEval'

// TODO: Implement
const useAuth = () => {
  // TODO
  const [isAuthenticated, setIsAuthenticated] = useState(true)
  const [isAdmin, setIsAdmin] = useState(false)

  return { isAuthenticated, isAdmin }
}

const NavLink = ({ to, children }: { to: string, children: React.ReactNode }) => (
  <Link
    to={to}
    className="flex items-center px-4 py-2 text-slate-700 dark:text-slate-300 rounded-md hover:bg-slate-200 dark:hover:bg-slate-700 [&.active]:bg-slate-200 dark:[&.active]:bg-slate-700 [&.active]:font-medium [&.active]:text-slate-900 dark:[&.active]:text-slate-100"
  >
    {children}
  </Link>
)

const NavLinkSeparator = () => (
  <div className="h-px bg-slate-200 dark:bg-slate-700 my-2"></div>
)

const UnauthenticatedNavLinks = () => (
  <>
    <NavLink to="/">Home</NavLink>
    <NavLink to="/login">Login</NavLink>
  </>
)

const AuthenticatedNavLinks = ({ isAdmin }: { isAdmin: boolean }) => (
  <>
    <NavLink to="/">Home</NavLink>
    <NavLink to="/namespaces">Namespaces</NavLink>
    {isAdmin && <AdminNavLinks />}
    <NavLinkSeparator />
    <NavLink to="/logout">Logout</NavLink>
  </>
)

const AdminNavLinks = () => (
  <>
    <NavLinkSeparator />
    <NavLink to="/users">Users</NavLink>
  </>
)

const PrettifyLabel = (label: string) => {
  return String(label) // Ensure currentLabel is a string before text manipulation
    .replace(/-/g, ' ')
    .replace(/([A-Z]+)/g, ' $1') // Add space before uppercase sequences (e.g. MyID -> My ID)
    .replace(/(\s[a-z])/g, (s) => s.toUpperCase()) // Capitalize words after spaces
    .trim()
    .replace(/^./, (str) => str.toUpperCase())
    .replace(/\sId$/, ' ID')
    .replace(/Id$/, 'ID');
}

// Breadcrumb component to show the current path hierarchy
const Breadcrumbs = () => {
  const matches = useMatches();
  console.log('Count Matches:', matches.length);
  console.log('Current matches:', JSON.stringify(matches, null, 2));
  const breadcrumbItems = [];

  if (matches.length <= 1) {
    return null;
  }

  for (const match of matches) {
    // Skip the root route itself
    if (match.id === '__root__') {
      continue;
    }

    // Skip the _auth layout route. Check for exact ID or ID with only a trailing slash.
    // This ensures that if _auth is purely a layout/grouping route, it's not a breadcrumb.
    if (match.id === '/_auth' || match.id === '/_auth/') {
      continue;
    }

    const params = match.params || {};

    // Clean the route ID for label parsing: remove /_auth prefix
    const routeIdForLabel = match.id.replace(/^\/_auth/, '');
    // Split into segments and filter out empty strings (from leading/trailing/double slashes)
    const pathSegments = routeIdForLabel.split('/').filter(Boolean);

    console.log('Path Segments:', pathSegments);

    // If, after cleaning, there are no path segments, this match doesn't represent a breadcrumb step.
    // This could happen if match.id was something like '/_auth' or '/_auth/' and wasn't caught by the specific skip above.
    if (pathSegments.length === 0) {
      continue;
    }

    // The last segment of the cleaned path usually determines the label for this breadcrumb item
    let labelSegment = pathSegments[pathSegments.length - 1];
    let currentLabel = labelSegment;

    // If the segment is a parameter (e.g., '$namespaceId'), replace it with its value
    if (labelSegment.startsWith('$')) {
      const paramName = labelSegment.substring(1);
      // Ensure paramName is valid and exists in params
      if (paramName && params[paramName]) {
        currentLabel = params[paramName];
      } else {
        // Fallback: use the param name itself (e.g., $namespaceId) if value is not found
        // Or, you might choose to display something else or log an error
        currentLabel = labelSegment;
      }
    }

    // Format the label for better readability
    currentLabel = String(currentLabel) // Ensure currentLabel is a string before text manipulation
      .replace(/-/g, ' ')
      .replace(/([A-Z]+)/g, ' $1') // Add space before uppercase sequences (e.g. MyID -> My ID)
      .replace(/(\s[a-z])/g, (s) => s.toUpperCase()) // Capitalize words after spaces
      .trim()
      .replace(/^./, (str) => str.toUpperCase())
      .replace(/\sId$/, ' ID')
      .replace(/Id$/, 'ID');

    breadcrumbItems.push({
      to: match.fullPath,
      params: params,
      label: currentLabel,
      key: match.pathname, // Use pathname for unique key per match instance
    });
  }

  if (breadcrumbItems.length === 0) {
    return null;
  }

  console.log('Breadcrumbs:', JSON.stringify(breadcrumbItems));

  return (
    <div className="flex items-center space-x-2 mb-4 text-sm">
      <Link
        to="/"
        className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
      >
        Home
      </Link>
      {breadcrumbItems.map((item, index) => (
        <div key={item.key} className="flex items-center space-x-2">
          <span className="text-gray-500 dark:text-gray-400">/</span>
          {index === breadcrumbItems.length - 1 ? (
            <span className="font-medium text-gray-700 dark:text-gray-300">
              {item.label}
            </span>
          ) : (
            <Link
              to={item.to}
              params={item.params}
              className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
            >
              {item.label}
            </Link>
          )}
        </div>
      ))}
    </div>
  );
}

export const Route = createRootRoute({
  component: () => {
    const { isAuthenticated, isAdmin } = useAuth()

    return (
      <div className="flex h-screen dark:bg-slate-900">
        {/* Sidebar */}
        <div className="w-64 bg-slate-50 dark:bg-slate-800 border-r border-slate-200 dark:border-slate-700 h-full flex flex-col">
          <div className="p-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
            <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">{appName}</h1>
            <ModeToggle />
          </div>
          <nav className="flex-1 p-4 space-y-2">
            {isAuthenticated
              ? <AuthenticatedNavLinks isAdmin={isAdmin} />
              : <UnauthenticatedNavLinks />
            }
          </nav>
        </div>

        {/* Main content */}
        <div className="flex-1 flex flex-col overflow-hidden dark:bg-slate-900">
          <main className="flex-1 overflow-y-auto p-6">
            <Breadcrumbs />
            <Outlet />
          </main>
          <TanStackRouterDevtools />
        </div>
      </div>
    )
  },
})
