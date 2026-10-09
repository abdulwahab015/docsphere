// Mirrors the API's rules for attached files (projects/constants.py and
// projects/mappings.py). The API checks each file's content; these only spare
// a person an upload that's bound to be refused.
export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

export const ATTACHMENT_ACCEPT = [
  '.pdf',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.webp',
  '.txt',
  '.csv',
  '.docx',
  '.xlsx',
  '.pptx',
].join(',')

export const ATTACHMENT_HINT =
  'PDF, PNG, JPEG, GIF, WebP, text, CSV, Word, Excel or PowerPoint, up to 10 MB.'
export const ATTACHMENT_TOO_LARGE_MESSAGE = 'Files can be at most 10 MB.'
