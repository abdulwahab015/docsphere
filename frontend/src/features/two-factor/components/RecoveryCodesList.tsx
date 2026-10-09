import { CopyIcon, DownloadIcon } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { fileSaver } from '@/lib/save-file'

const RECOVERY_CODES_FILE_NAME = 'docsphere-recovery-codes.txt'

/** Recovery codes, which the API shows only once: each one signs in once in
 * place of a code from the app. */
export function RecoveryCodesList({ codes }: { codes: string[] }) {
  const text = codes.join('\n')

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success('Recovery codes copied.')
    } catch {
      toast.error("Couldn't copy them. Download them instead.")
    }
  }

  const download = () =>
    fileSaver.save(new Blob([`${text}\n`], { type: 'text/plain' }), RECOVERY_CODES_FILE_NAME)

  return (
    <div className="flex flex-col gap-3">
      <ul
        aria-label="Recovery codes"
        className="grid grid-cols-2 gap-x-4 gap-y-1 rounded-md border bg-muted p-3 font-mono text-sm"
      >
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => void copy()}>
          <CopyIcon aria-hidden />
          Copy
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={download}>
          <DownloadIcon aria-hidden />
          Download
        </Button>
      </div>
    </div>
  )
}
