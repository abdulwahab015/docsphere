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

/** A download asks for an `arraybuffer`, so an error's body - the API's
 * reason, as JSON - arrives as bytes too. Decoded here, a failed download
 * reads like any other failed request. */
apiClient.interceptors.response.use(undefined, (error: unknown) => {
  if (isAxiosError(error) && error.response && error.config?.responseType === 'arraybuffer') {
    try {
      error.response.data = JSON.parse(new TextDecoder().decode(error.response.data))
    } catch {
      // Not JSON (a proxy's error page, say): left as it came.
    }
  }
  throw error
})

apiClient.interceptors.response.use(undefined, async (error: unknown) => {
  if (!isAxiosError(error) || !error.config) {
    throw error
  }
  const { config } = error

  // A 401 on a request that carried no token (e.g. wrong login credentials)
  // is an answer, not an expired session.
  const tokenRejected =
    error.response?.status === HTTP_STATUS.unauthorized && Boolean(config.headers.Authorization)
  if (!tokenRejected || config.isReplayAfterRefresh) {
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
