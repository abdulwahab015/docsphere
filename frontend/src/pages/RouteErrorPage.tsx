import { Button } from '@/components/ui/button'
import { usePageTitle } from '@/hooks/use-page-title'

/** Shown when rendering a page throws, instead of a blank screen. */
export function RouteErrorPage() {
  usePageTitle('Something went wrong')

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 p-4 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Something went wrong</h1>
      <p className="text-muted-foreground">
        An unexpected error stopped this page from loading. Reloading usually fixes it.
      </p>
      <Button onClick={() => window.location.reload()}>Reload page</Button>
    </main>
  )
}
