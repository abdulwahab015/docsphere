// Paths the backend puts in emails (acceptInvite, resetPassword) must keep
// their exact shape.
export const PATHS = {
  home: '/',
  login: '/login',
  signup: '/signup',
  forgotPassword: '/forgot-password',
  resetPassword: '/reset-password',
  acceptInvite: '/accept-invite',
  people: '/people',
  organizationSettings: '/settings/organization',
} as const
