import type { ComponentProps } from 'react'

import type { AccessLevel } from '@/api/types'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { ACCESS_LEVEL_LABELS, ACCESS_LEVELS } from '@/lib/access'

interface AccessLevelSelectProps extends Omit<
  ComponentProps<typeof NativeSelect>,
  'value' | 'onChange'
> {
  value: AccessLevel
  onChange: (level: AccessLevel) => void
}

export function AccessLevelSelect({ value, onChange, ...selectProps }: AccessLevelSelectProps) {
  return (
    <NativeSelect
      size="sm"
      value={value}
      // The options are ACCESS_LEVELS in order, so the selected index names the level.
      onChange={(event) => onChange(ACCESS_LEVELS[event.target.selectedIndex])}
      {...selectProps}
    >
      {ACCESS_LEVELS.map((level) => (
        <NativeSelectOption key={level} value={level}>
          {ACCESS_LEVEL_LABELS[level]}
        </NativeSelectOption>
      ))}
    </NativeSelect>
  )
}
