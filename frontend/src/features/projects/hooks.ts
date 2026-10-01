import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { ListParams, Project, ProjectUpdatePayload } from '@/api/types'
import {
  createProject,
  deleteProject,
  fetchProject,
  listProjects,
  listProjectTrash,
  restoreProject,
  updateProject,
} from '@/features/projects/api'
import { projectKeys } from '@/features/projects/query-keys'

export function useProjects(params: ListParams) {
  return useQuery({
    queryKey: projectKeys.list(params),
    queryFn: () => listProjects(params),
    placeholderData: keepPreviousData,
  })
}

export function useProject(projectId: number) {
  return useQuery({
    queryKey: projectKeys.detail(projectId),
    queryFn: () => fetchProject(projectId),
  })
}

export function useProjectTrash(page: number) {
  return useQuery({
    queryKey: projectKeys.trash(page),
    queryFn: () => listProjectTrash({ page }),
    placeholderData: keepPreviousData,
  })
}

/** Caches a project the API just returned, and marks every list stale. */
function useStoreProject() {
  const queryClient = useQueryClient()
  return (project: Project) => {
    queryClient.setQueryData(projectKeys.detail(project.id), project)
    void queryClient.invalidateQueries({ queryKey: projectKeys.lists() })
  }
}

export function useCreateProject() {
  const storeProject = useStoreProject()
  return useMutation({ mutationFn: createProject, onSuccess: storeProject })
}

export function useUpdateProject(projectId: number) {
  const storeProject = useStoreProject()
  return useMutation({
    mutationFn: (payload: ProjectUpdatePayload) => updateProject(projectId, payload),
    onSuccess: storeProject,
  })
}

export function useDeleteProject(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => deleteProject(projectId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: projectKeys.detail(projectId) })
      void queryClient.invalidateQueries({ queryKey: projectKeys.all })
    },
  })
}

export function useRestoreProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: restoreProject,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: projectKeys.all }),
  })
}
