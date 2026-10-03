import { PageHeader } from '@/components/PageHeader'
import { ChangePasswordForm } from '@/features/account/components/ChangePasswordForm'
import { ProfileCard } from '@/features/account/components/ProfileCard'

export function AccountPage() {
  return (
    <>
      <PageHeader title="Account" description="Your sign-in details and password." />
      <div className="flex flex-col gap-6">
        <ProfileCard />
        <ChangePasswordForm />
      </div>
    </>
  )
}
