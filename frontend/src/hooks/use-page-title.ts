import { useEffect } from 'react'

export const APP_NAME = 'DocSphere'

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · ${APP_NAME}`
  }, [title])
}
