import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'

import { DEFAULT_PAGE_SIZE } from '@/api/constants'
import { Button } from '@/components/ui/button'

interface PaginationProps {
  page: number
  count: number
  onPageChange: (page: number) => void
  pageSize?: number
}

export function Pagination({
  page,
  count,
  onPageChange,
  pageSize = DEFAULT_PAGE_SIZE,
}: PaginationProps) {
  const pageCount = Math.max(1, Math.ceil(count / pageSize))
  const firstItem = count ? (page - 1) * pageSize + 1 : 0
  const lastItem = Math.min(page * pageSize, count)

  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-4 text-sm">
      <p className="text-muted-foreground">
        {count ? `Showing ${firstItem}–${lastItem} of ${count}` : 'No results'}
      </p>
      {pageCount > 1 && (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeftIcon aria-hidden />
            Previous
          </Button>
          <span className="text-muted-foreground">
            Page {page} of {pageCount}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pageCount}
            onClick={() => onPageChange(page + 1)}
          >
            Next
            <ChevronRightIcon aria-hidden />
          </Button>
        </div>
      )}
    </nav>
  )
}
