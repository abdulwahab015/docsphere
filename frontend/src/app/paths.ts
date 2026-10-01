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
  people: '/people',
  organizationSettings: '/settings/organization',
} as const

export function projectPath(projectId: number) {
  return `${PATHS.projects}/${projectId}`
}
