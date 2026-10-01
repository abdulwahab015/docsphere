import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { authKeys } from '@/features/auth/query-keys'
import { fetchOrganization, updateOrganization } from '@/features/organization/api'
import { organizationKeys } from '@/features/organization/query-keys'

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
