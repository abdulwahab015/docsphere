import type { ExcerptSegment } from '@/api/types'

/** Where a search matched inside a document, under its title in the list:
 * the API's excerpt, with the matching words marked. */
export function SearchExcerpt({ segments }: { segments: ExcerptSegment[] }) {
  return (
    <p className="mt-1 line-clamp-2 max-w-xl text-sm font-normal whitespace-normal text-muted-foreground">
      {segments.map((segment, index) =>
        segment.match ? (
          <mark key={index} className="rounded-sm bg-primary/15 px-0.5 text-foreground">
            {segment.text}
          </mark>
        ) : (
          <span key={index}>{segment.text}</span>
        ),
      )}
    </p>
  )
}
