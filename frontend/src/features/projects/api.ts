import { apiClient } from '@/api/client'
import type {
  ListParams,
  Paginated,
  Project,
  ProjectCreatePayload,
  ProjectUpdatePayload,
} from '@/api/types'

const PROJECTS_PATH = '/projects/'

function projectPath(projectId: number) {
  return `${PROJECTS_PATH}${projectId}/`
}

export async function listProjects({ page, search }: ListParams) {
  const { data } = await apiClient.get<Paginated<Project>>(PROJECTS_PATH, {
    params: { page, search: search || undefined },
  })
  return data
}

export async function fetchProject(projectId: number) {
  const { data } = await apiClient.get<Project>(projectPath(projectId))
  return data
}

export async function createProject(payload: ProjectCreatePayload) {
  const { data } = await apiClient.post<Project>(PROJECTS_PATH, payload)
  return data
}

export async function updateProject(projectId: number, payload: ProjectUpdatePayload) {
  const { data } = await apiClient.patch<Project>(projectPath(projectId), payload)
  return data
}

/** A soft delete: the project moves to the trash, where an admin can restore it. */
export async function deleteProject(projectId: number) {
  await apiClient.delete(projectPath(projectId))
}

export async function listProjectTrash({ page }: Pick<ListParams, 'page'>) {
  const { data } = await apiClient.get<Paginated<Project>>(`${PROJECTS_PATH}trash/`, {
    params: { page },
  })
  return data
}

export async function restoreProject(projectId: number) {
  const { data } = await apiClient.post<Project>(`${projectPath(projectId)}restore/`)
  return data
}
