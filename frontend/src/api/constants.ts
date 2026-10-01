import { env } from '@/lib/env'

export const API_ROOT = `${env.VITE_API_BASE_URL}/api/v1`

export const REFRESH_PATH = '/users/auth/refresh/'

// Mirrors the backend's PageNumberPagination.page_size.
export const DEFAULT_PAGE_SIZE = 20

export const HTTP_STATUS = {
  badRequest: 400,
  unauthorized: 401,
  paymentRequired: 402,
  forbidden: 403,
  notFound: 404,
  serverError: 500,
} as const
