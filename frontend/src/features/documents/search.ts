// The documents list's search covers what's inside documents, not just titles.
export const DOCUMENT_SEARCH_PLACEHOLDER = 'Search titles and content'

export function noDocumentMatches(search: string) {
  return `No document mentions "${search}" in its title or content.`
}
