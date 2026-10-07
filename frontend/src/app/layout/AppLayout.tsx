import { Outlet } from 'react-router'

import { AppSidebar } from '@/app/layout/AppSidebar'
import { Separator } from '@/components/ui/separator'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useSignedInMember } from '@/features/auth/hooks'
import { PaymentFailedBanner } from '@/features/billing/components/PaymentFailedBanner'

/** The signed-in app's frame: sidebar navigation, a top bar, and the page. */
export function AppLayout() {
  const user = useSignedInMember()

  // TooltipProvider: the sidebar labels its icons with tooltips when collapsed.
  return (
    <TooltipProvider>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
            <SidebarTrigger aria-label="Toggle navigation" />
            <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
            <span className="truncate text-sm font-medium">{user.organization.name}</span>
          </header>
          <main className="flex flex-1 flex-col gap-6 p-4 md:p-6">
            <PaymentFailedBanner />
            <Outlet />
          </main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
