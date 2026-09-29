import { LogoutButton } from '@/features/auth/components/LogoutButton'
import { useSignedInUser } from '@/features/auth/hooks'

// Placeholder until the app shell (sidebar, projects, documents) replaces it.
export function HomePage() {
  const user = useSignedInUser()

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 p-4 text-center">
      <h1 className="text-3xl font-semibold tracking-tight">DocSphere</h1>
      <p className="text-muted-foreground">
        Signed in as {user.email} · {user.organization.name}
      </p>
      <LogoutButton />
    </main>
  )
}
