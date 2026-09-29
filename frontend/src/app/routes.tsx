import type { RouteObject } from 'react-router'

import { PATHS } from '@/app/paths'
import { RequireActiveSubscription } from '@/features/auth/components/RequireActiveSubscription'
import { RequireAuth } from '@/features/auth/components/RequireAuth'
import { RequireGuest } from '@/features/auth/components/RequireGuest'
import { AcceptInvitePage } from '@/features/auth/pages/AcceptInvitePage'
import { ForgotPasswordPage } from '@/features/auth/pages/ForgotPasswordPage'
import { LoginPage } from '@/features/auth/pages/LoginPage'
import { ResetPasswordPage } from '@/features/auth/pages/ResetPasswordPage'
import { SignupPage } from '@/features/auth/pages/SignupPage'
import { HomePage } from '@/pages/HomePage'
import { NotFoundPage } from '@/pages/NotFoundPage'

export const routes: RouteObject[] = [
  {
    element: <RequireGuest />,
    children: [
      { path: PATHS.login, element: <LoginPage /> },
      { path: PATHS.signup, element: <SignupPage /> },
      { path: PATHS.forgotPassword, element: <ForgotPasswordPage /> },
    ],
  },
  // Opened from emailed links, so reachable whether or not someone is signed in.
  { path: PATHS.resetPassword, element: <ResetPasswordPage /> },
  { path: PATHS.acceptInvite, element: <AcceptInvitePage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <RequireActiveSubscription />,
        children: [{ path: PATHS.home, element: <HomePage /> }],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
]
