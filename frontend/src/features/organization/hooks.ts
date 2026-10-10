import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { authKeys } from '@/features/auth/query-keys'
import {
  deleteOrganization,
  downloadExport,
  fetchOrganization,
  requestExport,
  restoreOrganization,
  updateOrganization,
} from '@/features/organization/api'
import { organizationKeys } from '@/features/organization/query-keys'
import { fileSaver } from '@/lib/save-file'

// The name the downloaded export is saved under.
const EXPORT_FILE_NAME = 'docsphere-export.zip'

export function useOrganization() {
  return useQuery({ queryKey: organizationKeys.profile, queryFn: fetchOrganization })
}

export function useUpdateOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateOrganization,
    onSuccess: (organization) => {
      queryClient.setQueryData(organizationKeys.profile, organization)
      // The session carries the organization's name too (sidebar, top bar).
      void queryClient.invalidateQueries({ queryKey: authKeys.currentUser })
    },
  })
}

/** Deleting or restoring the organization changes what the whole app shows,
 * so both re-read the session, whose organization says whether it's deleted. */
function useRereadSession() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: authKeys.currentUser })
}

export function useDeleteOrganization() {
  const rereadSession = useRereadSession()
  return useMutation({ mutationFn: deleteOrganization, onSuccess: rereadSession })
}

export function useRestoreOrganization() {
  const rereadSession = useRereadSession()
  return useMutation({ mutationFn: restoreOrganization, onSuccess: rereadSession })
}

export function useRequestExport() {
  return useMutation({ mutationFn: requestExport })
}

export function useDownloadExport() {
  return useMutation({
    mutationFn: async (token: string) =>
      fileSaver.save(await downloadExport(token), EXPORT_FILE_NAME),
  })
}
