import type { Visibility } from '@/api/types'

export function projectVisibilityDescriptions(
  organizationName: string,
): Record<Visibility, string> {
  return {
    PRIVATE: 'Only people you share it with can see it.',
    PUBLIC: `Everyone in ${organizationName} can view it.`,
  }
}
