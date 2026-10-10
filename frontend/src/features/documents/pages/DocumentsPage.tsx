import { FileTextIcon, Trash2Icon } from 'lucide-react'
import { Link } from 'react-router'

import { PATHS } from '@/app/paths'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Pagination } from '@/components/Pagination'
import { SearchInput } from '@/components/SearchInput'
import { Button } from '@/components/ui/button'
import { CreateDocumentDialog } from '@/features/documents/components/CreateDocumentDialog'
import { DocumentsTable } from '@/features/documents/components/DocumentsTable'
import { useDocuments } from '@/features/documents/hooks'
import { DOCUMENT_SEARCH_PLACEHOLDER, noDocumentMatches } from '@/features/documents/search'
import { useListParams } from '@/hooks/use-list-params'

export function DocumentsPage() {
  const { page, search, setPage, setSearch } = useListParams()
  const documents = useDocuments({ page, search })

  return (
    <>
      <PageHeader
        title="Documents"
        description="Documents you can open, from every project and your personal ones."
        actions={
          <>
            <Button asChild variant="outline">
              <Link to={PATHS.documentTrash}>
                <Trash2Icon aria-hidden />
                Trash
              </Link>
            </Button>
            <CreateDocumentDialog />
          </>
        }
      />
      <SearchInput
        value={search}
        onSearch={setSearch}
        label="Search documents"
        placeholder={DOCUMENT_SEARCH_PLACEHOLDER}
      />
      {documents.isError ? (
        <ErrorState error={documents.error} onRetry={() => void documents.refetch()} />
      ) : documents.data && !documents.data.count ? (
        <EmptyState
          icon={FileTextIcon}
          title={search ? 'No matches' : 'No documents yet'}
          description={
            search
              ? noDocumentMatches(search)
              : 'Create a personal document, or open a project to add one there.'
          }
        />
      ) : (
        <>
          <DocumentsTable
            documents={documents.data}
            isFetching={documents.isFetching}
            markPersonal
          />
          {documents.data && (
            <Pagination page={page} count={documents.data.count} onPageChange={setPage} />
          )}
        </>
      )}
    </>
  )
}
