import type { MyAccessRequestParams, SharedResource } from '@/features/sharing/api'

export const sharingKeys = {
  all: ['sharing'] as const,
  grants: ({ kind, id }: SharedResource) => [...sharingKeys.all, kind, id] as const,
  grantsPage: (resource: SharedResource, page: number) =>
    [...sharingKeys.grants(resource), page] as const,
}

export const accessRequestKeys = {
  all: ['access-requests'] as const,
  incomingLists: () => [...accessRequestKeys.all, 'incoming'] as const,
  incoming: (page: number) => [...accessRequestKeys.incomingLists(), page] as const,
  mine: (params: MyAccessRequestParams) => [...accessRequestKeys.all, 'mine', params] as const,
}
