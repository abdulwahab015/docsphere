import { Navigate, type RouteObject } from 'react-router'

import { AppLayout } from '@/app/layout/AppLayout'
import { RootLayout } from '@/app/layout/RootLayout'
import { PATHS } from '@/app/paths'
import { RequireActiveSubscription } from '@/features/auth/components/RequireActiveSubscription'
import { RequireAuth } from '@/features/auth/components/RequireAuth'
import { RequireGuest } from '@/features/auth/components/RequireGuest'
import { RequireOrgAdmin } from '@/features/auth/components/RequireOrgAdmin'
import { AcceptInvitePage } from '@/features/auth/pages/AcceptInvitePage'
import { ForgotPasswordPage } from '@/features/auth/pages/ForgotPasswordPage'
import { LoginPage } from '@/features/auth/pages/LoginPage'
import { ResetPasswordPage } from '@/features/auth/pages/ResetPasswordPage'
import { SignupPage } from '@/features/auth/pages/SignupPage'
import { OrganizationSettingsPage } from '@/features/organization/pages/OrganizationSettingsPage'
import { PeoplePage } from '@/features/people/pages/PeoplePage'
import { DocumentPage } from '@/features/documents/pages/DocumentPage'
import { DocumentsPage } from '@/features/documents/pages/DocumentsPage'
import { DocumentTrashPage } from '@/features/documents/pages/DocumentTrashPage'
import { ProjectDetailPage } from '@/features/projects/pages/ProjectDetailPage'
import { ProjectsPage } from '@/features/projects/pages/ProjectsPage'
import { ProjectTrashPage } from '@/features/projects/pages/ProjectTrashPage'
import { RequestsPage } from '@/features/sharing/pages/RequestsPage'
import { RouteErrorPage } from '@/pages/RouteErrorPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

export const routes: RouteObject[] = [
  {
    element: <RootLayout />,
    errorElement: <RouteErrorPage />,
    children: [
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
            children: [
              {
                element: <AppLayout />,
                children: [
                  { path: PATHS.home, element: <Navigate to={PATHS.projects} replace /> },
                  { path: PATHS.projects, element: <ProjectsPage /> },
                  { path: PATHS.projectDetail, element: <ProjectDetailPage /> },
                  { path: PATHS.documents, element: <DocumentsPage /> },
                  { path: PATHS.documentTrash, element: <DocumentTrashPage /> },
                  { path: PATHS.documentDetail, element: <DocumentPage /> },
                  { path: PATHS.accessRequests, element: <RequestsPage /> },
                  { path: PATHS.people, element: <PeoplePage /> },
                  {
                    element: <RequireOrgAdmin />,
                    children: [
                      { path: PATHS.projectTrash, element: <ProjectTrashPage /> },
                      {
                        path: PATHS.organizationSettings,
                        element: <OrganizationSettingsPage />,
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
