// Paths the backend sends people to (acceptInvite, resetPassword, verifyEmail
// and confirmEmail in emails; billing, billingSuccess and billingCancel as
// Stripe's return addresses) must keep their exact shape.
export const PATHS = {
  home: '/',
  login: '/login',
  signup: '/signup',
  forgotPassword: '/forgot-password',
  resetPassword: '/reset-password',
  acceptInvite: '/accept-invite',
  verifyEmail: '/verify-email',
  confirmEmail: '/confirm-email',
  projects: '/projects',
  projectDetail: '/projects/:projectId',
  projectTrash: '/projects/trash',
  documents: '/documents',
  documentDetail: '/documents/:documentId',
  documentTrash: '/documents/trash',
  accessRequests: '/requests',
  people: '/people',
  organizationSettings: '/settings/organization',
  account: '/settings/account',
  billing: '/billing',
  billingSuccess: '/billing/success',
  billingCancel: '/billing/cancel',
} as const

export function projectPath(projectId: number) {
  return `${PATHS.projects}/${projectId}`
}

export function documentPath(documentId: number) {
  return `${PATHS.documents}/${documentId}`
}
