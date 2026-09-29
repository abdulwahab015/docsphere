import { create as createAxiosInstance, isAxiosError } from 'axios'

import { clearAccessToken, getAccessToken, refreshAccessToken } from '@/api/access-token'
import { API_ROOT, HTTP_STATUS } from '@/api/constants'

declare module 'axios' {
  interface AxiosRequestConfig {
    /** Set on a request replayed after a token refresh, so a second 401 is final. */
    isReplayAfterRefresh?: boolean
  }
}

export const apiClient = createAxiosInstance({
  baseURL: API_ROOT,
  withCredentials: true,
})

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(undefined, async (error: unknown) => {
  const config = isAxiosError(error) ? error.config : undefined
  const expiredToken =
    isAxiosError(error) &&
    error.response?.status === HTTP_STATUS.unauthorized &&
    config?.headers.Authorization

  // A 401 on a request that carried no token (e.g. wrong login credentials)
  // is an answer, not an expired session.
  if (!config || !expiredToken || config.isReplayAfterRefresh) {
    throw error
  }

  try {
    await refreshAccessToken()
  } catch {
    clearAccessToken()
    throw error
  }

  return apiClient({ ...config, isReplayAfterRefresh: true })
})
