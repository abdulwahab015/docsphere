import type { Visibility } from '@/api/types'
import { Field, FieldDescription, FieldLabel, FieldSet, FieldLegend } from '@/components/ui/field'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { VISIBILITY_LABELS } from '@/lib/access'

interface VisibilityFieldProps {
  value: Visibility
  onChange: (visibility: Visibility) => void
  /** What each choice means for this kind of resource. */
  descriptions: Record<Visibility, string>
}

const OPTIONS: Visibility[] = ['PRIVATE', 'PUBLIC']

export function VisibilityField({ value, onChange, descriptions }: VisibilityFieldProps) {
  return (
    <FieldSet>
      <FieldLegend variant="label">Visibility</FieldLegend>
      <RadioGroup value={value} onValueChange={(next) => onChange(next as Visibility)}>
        {OPTIONS.map((option) => (
          <Field key={option} orientation="horizontal" className="items-start">
            <RadioGroupItem value={option} id={`visibility-${option}`} />
            <div className="flex flex-col gap-0.5">
              <FieldLabel htmlFor={`visibility-${option}`}>{VISIBILITY_LABELS[option]}</FieldLabel>
              <FieldDescription>{descriptions[option]}</FieldDescription>
            </div>
          </Field>
        ))}
      </RadioGroup>
    </FieldSet>
  )
}
