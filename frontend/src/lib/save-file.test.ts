import { fileSaver } from '@/lib/save-file'

describe('fileSaver', () => {
  it('hands the file to the browser as a download under its name, then lets it go', () => {
    vi.useFakeTimers()
    const createObjectURL = vi.fn<(file: Blob) => string>(() => 'blob:report')
    const revokeObjectURL = vi.fn<(url: string) => void>()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      expect(this.href).toBe('blob:report')
      expect(this.download).toBe('Q3 report.pdf')
    })
    const file = new Blob(['%PDF-1.7'])

    fileSaver.save(file, 'Q3 report.pdf')

    expect(createObjectURL).toHaveBeenCalledWith(file)
    expect(click).toHaveBeenCalledOnce()
    expect(revokeObjectURL).not.toHaveBeenCalled()
    vi.runAllTimers()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:report')
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })
})
