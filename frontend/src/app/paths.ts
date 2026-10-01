// Paths the backend puts in emails (acceptInvite, resetPassword) must keep
// their exact shape.
export const PATHS = {
  home: '/',
  login: '/login',
  signup: '/signup',
  forgotPassword: '/forgot-password',
  resetPassword: '/reset-password',
  acceptInvite: '/accept-invite',
  projects: '/projects',
  projectDetail: '/projects/:projectId',
  projectTrash: '/projects/trash',
  documents: '/documents',
  documentDetail: '/documents/:documentId',
  documentTrash: '/documents/trash',
  people: '/people',
  organizationSettings: '/settings/organization',
} as const

export function projectPath(projectId: number) {
  return `${PATHS.projects}/${projectId}`
}

export function documentPath(documentId: number) {
  return `${PATHS.documents}/${documentId}`
}
