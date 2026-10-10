// How long the browser keeps a downloaded file's object URL once the download
// has started.
const OBJECT_URL_LIFETIME_MS = 1000

/** Hands a file the app fetched itself to the browser as a download - for
 * files behind the API's sign-in, which a plain link couldn't fetch. An object
 * rather than a bare function so tests can spy on it, since jsdom can't
 * download. */
export const fileSaver = {
  save(file: Blob, name: string) {
    const url = URL.createObjectURL(file)
    const link = document.createElement('a')
    link.href = url
    link.download = name
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), OBJECT_URL_LIFETIME_MS)
  },
}
