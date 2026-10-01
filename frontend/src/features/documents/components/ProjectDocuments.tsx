import { FileTextIcon } from 'lucide-react'

import type { Project } from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { Pagination } from '@/components/Pagination'
import { SearchInput } from '@/components/SearchInput'
import { CreateDocumentDialog } from '@/features/documents/components/CreateDocumentDialog'
import { DocumentsTable } from '@/features/documents/components/DocumentsTable'
import { useDocuments } from '@/features/documents/hooks'
import { useListParams } from '@/hooks/use-list-params'
import { can } from '@/lib/access'

/** A project's documents - only the ones the reader can open themselves:
 * access to a project grants nothing on the documents inside it. */
export function ProjectDocuments({ project }: { project: Project }) {
  const { page, search, setPage, setSearch } = useListParams()
  const documents = useDocuments({ page, search, project: project.id })

  return (
    <section aria-labelledby="project-documents" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 id="project-documents" className="text-lg font-semibold">
            Documents
          </h2>
          <p className="text-sm text-muted-foreground">
            Each document is shared on its own: access to this project doesn&apos;t include the
            documents in it.
          </p>
        </div>
        {/* Adding a document to a project takes Editor access to the project. */}
        {can(project.access_level, 'WRITE') && <CreateDocumentDialog project={project} />}
      </div>
      <SearchInput
        value={search}
        onSearch={setSearch}
        label="Search this project's documents"
        placeholder="Search by title"
      />
      {documents.isError ? (
        <ErrorState error={documents.error} onRetry={() => void documents.refetch()} />
      ) : documents.data && !documents.data.count ? (
        <EmptyState
          icon={FileTextIcon}
          title={search ? 'No matches' : 'No documents you can open'}
          description={
            search
              ? `No document's title matches "${search}".`
              : 'Documents in this project appear here once you have access to them.'
          }
        />
      ) : (
        <>
          <DocumentsTable documents={documents.data} isFetching={documents.isFetching} />
          {documents.data && (
            <Pagination page={page} count={documents.data.count} onPageChange={setPage} />
          )}
        </>
      )}
    </section>
  )
}
