import { PageHeader } from '@/components/PageHeader'
import { ChangeEmailForm } from '@/features/account/components/ChangeEmailForm'
import { ChangePasswordForm } from '@/features/account/components/ChangePasswordForm'
import { DeleteAccountCard } from '@/features/account/components/DeleteAccountCard'
import { NameForm } from '@/features/account/components/NameForm'
import { ProfileCard } from '@/features/account/components/ProfileCard'

export function AccountPage() {
  return (
    <>
      <PageHeader
        title="Account"
        description="Your name, sign-in details and password, or deleting your account."
      />
      <div className="flex flex-col gap-6">
        <NameForm />
        <ProfileCard />
        <ChangeEmailForm />
        <ChangePasswordForm />
        <DeleteAccountCard />
      </div>
    </>
  )
}
