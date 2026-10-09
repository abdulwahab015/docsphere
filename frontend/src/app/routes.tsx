import type { ComponentType } from 'react'
import { Navigate, type RouteObject } from 'react-router'

import { AppLayout } from '@/app/layout/AppLayout'
import { RootLayout } from '@/app/layout/RootLayout'
import { PATHS } from '@/app/paths'
import { FullPageSpinner } from '@/components/FullPageSpinner'
import { RequireActiveSubscription } from '@/features/auth/components/RequireActiveSubscription'
import { RequireAuth } from '@/features/auth/components/RequireAuth'
import { RequireGuest } from '@/features/auth/components/RequireGuest'
import { RequireOrgAdmin } from '@/features/auth/components/RequireOrgAdmin'
import { RequireVerifiedEmail } from '@/features/auth/components/RequireVerifiedEmail'
import { RouteErrorPage } from '@/pages/RouteErrorPage'

/** Loads a page's code the first time its route is visited, so each page is a
 * chunk of its own rather than part of the bundle everyone downloads first. */
function lazyPage<TModule>(
  load: () => Promise<TModule>,
  pickPage: (module: TModule) => ComponentType,
) {
  return async () => ({ Component: pickPage(await load()) })
}

export const routes: RouteObject[] = [
  {
    element: <RootLayout />,
    errorElement: <RouteErrorPage />,
    // Shown while the first page's code loads.
    hydrateFallbackElement: <FullPageSpinner />,
    children: [
      {
        element: <RequireGuest />,
        children: [
          {
            path: PATHS.login,
            lazy: lazyPage(
              () => import('@/features/auth/pages/LoginPage'),
              (module) => module.LoginPage,
            ),
          },
          {
            path: PATHS.signup,
            lazy: lazyPage(
              () => import('@/features/auth/pages/SignupPage'),
              (module) => module.SignupPage,
            ),
          },
          {
            path: PATHS.forgotPassword,
            lazy: lazyPage(
              () => import('@/features/auth/pages/ForgotPasswordPage'),
              (module) => module.ForgotPasswordPage,
            ),
          },
        ],
      },
      // Opened from emailed links, so reachable whether or not someone is signed in.
      {
        path: PATHS.resetPassword,
        lazy: lazyPage(
          () => import('@/features/auth/pages/ResetPasswordPage'),
          (module) => module.ResetPasswordPage,
        ),
      },
      {
        path: PATHS.acceptInvite,
        lazy: lazyPage(
          () => import('@/features/auth/pages/AcceptInvitePage'),
          (module) => module.AcceptInvitePage,
        ),
      },
      {
        path: PATHS.verifyEmail,
        lazy: lazyPage(
          () => import('@/features/auth/pages/VerifyEmailPage'),
          (module) => module.VerifyEmailPage,
        ),
      },
      {
        path: PATHS.confirmEmail,
        lazy: lazyPage(
          () => import('@/features/auth/pages/ConfirmEmailPage'),
          (module) => module.ConfirmEmailPage,
        ),
      },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <RequireVerifiedEmail />,
            children: [
              // Stripe Checkout's return addresses: reached before the subscription is
              // active (the webhook confirming it may still be on its way).
              {
                path: PATHS.billingSuccess,
                lazy: lazyPage(
                  () => import('@/features/billing/pages/CheckoutSuccessPage'),
                  (module) => module.CheckoutSuccessPage,
                ),
              },
              {
                path: PATHS.billingCancel,
                lazy: lazyPage(
                  () => import('@/features/billing/pages/CheckoutCancelPage'),
                  (module) => module.CheckoutCancelPage,
                ),
              },
              {
                element: <RequireActiveSubscription />,
                children: [
                  {
                    element: <AppLayout />,
                    children: [
                      { path: PATHS.home, element: <Navigate to={PATHS.projects} replace /> },
                      {
                        path: PATHS.projects,
                        lazy: lazyPage(
                          () => import('@/features/projects/pages/ProjectsPage'),
                          (module) => module.ProjectsPage,
                        ),
                      },
                      {
                        path: PATHS.projectDetail,
                        lazy: lazyPage(
                          () => import('@/features/projects/pages/ProjectDetailPage'),
                          (module) => module.ProjectDetailPage,
                        ),
                      },
                      {
                        path: PATHS.documents,
                        lazy: lazyPage(
                          () => import('@/features/documents/pages/DocumentsPage'),
                          (module) => module.DocumentsPage,
                        ),
                      },
                      {
                        path: PATHS.documentTrash,
                        lazy: lazyPage(
                          () => import('@/features/documents/pages/DocumentTrashPage'),
                          (module) => module.DocumentTrashPage,
                        ),
                      },
                      {
                        path: PATHS.documentDetail,
                        lazy: lazyPage(
                          () => import('@/features/documents/pages/DocumentPage'),
                          (module) => module.DocumentPage,
                        ),
                      },
                      {
                        path: PATHS.accessRequests,
                        lazy: lazyPage(
                          () => import('@/features/sharing/pages/RequestsPage'),
                          (module) => module.RequestsPage,
                        ),
                      },
                      {
                        path: PATHS.people,
                        lazy: lazyPage(
                          () => import('@/features/people/pages/PeoplePage'),
                          (module) => module.PeoplePage,
                        ),
                      },
                      {
                        path: PATHS.account,
                        lazy: lazyPage(
                          () => import('@/features/account/pages/AccountPage'),
                          (module) => module.AccountPage,
                        ),
                      },
                      {
                        element: <RequireOrgAdmin />,
                        children: [
                          {
                            path: PATHS.projectTrash,
                            lazy: lazyPage(
                              () => import('@/features/projects/pages/ProjectTrashPage'),
                              (module) => module.ProjectTrashPage,
                            ),
                          },
                          {
                            path: PATHS.organizationSettings,
                            lazy: lazyPage(
                              () =>
                                import('@/features/organization/pages/OrganizationSettingsPage'),
                              (module) => module.OrganizationSettingsPage,
                            ),
                          },
                          {
                            path: PATHS.billing,
                            lazy: lazyPage(
                              () => import('@/features/billing/pages/BillingPage'),
                              (module) => module.BillingPage,
                            ),
                          },
                          {
                            path: PATHS.activity,
                            lazy: lazyPage(
                              () => import('@/features/activity/pages/ActivityPage'),
                              (module) => module.ActivityPage,
                            ),
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        path: '*',
        lazy: lazyPage(
          () => import('@/pages/NotFoundPage'),
          (module) => module.NotFoundPage,
        ),
      },
    ],
  },
]
