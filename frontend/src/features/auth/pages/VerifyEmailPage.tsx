import { useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router'

import { actionErrorMessage, UNEXPECTED_ERROR_MESSAGE } from '@/api/errors'
import { PATHS } from '@/app/paths'
import { FullPageSpinner } from '@/components/FullPageSpinner'
import { TextLink } from '@/components/TextLink'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { useVerifyEmail } from '@/features/auth/hooks'

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  if (!token) {
    return (
      <AuthCard
        title="Invalid verification link"
        description="This verification link is incomplete. Use the full link from your email."
      />
    )
  }

  return <EmailVerification token={token} />
}

/** Verifies as soon as the link is opened: doing it twice changes nothing,
 * so there's nothing to confirm first. */
function EmailVerification({ token }: { token: string }) {
  const { mutate, isSuccess, isError, error } = useVerifyEmail()
  const started = useRef(false)

  useEffect(() => {
    // Once, although React runs effects twice in development.
    if (!started.current) {
      started.current = true
      mutate({ token })
    }
  }, [mutate, token])

  if (isSuccess) {
    return (
      <AuthCard
        title="Email verified"
        description="Thanks - your email address is verified."
        footer={<TextLink to={PATHS.home}>Continue to DocSphere</TextLink>}
      />
    )
  }
  if (isError) {
    return (
      <AuthCard
        title="Couldn't verify your email"
        description={actionErrorMessage(error, UNEXPECTED_ERROR_MESSAGE)}
        footer={<TextLink to={PATHS.home}>Log in to get a new link</TextLink>}
      />
    )
  }
  return <FullPageSpinner />
}
