import type { RouteObject } from 'react-router'

import { PATHS } from '@/app/paths'
import { HomePage } from '@/pages/HomePage'
import { NotFoundPage } from '@/pages/NotFoundPage'

export const routes: RouteObject[] = [
  { path: PATHS.home, element: <HomePage /> },
  { path: '*', element: <NotFoundPage /> },
]
