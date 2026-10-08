/** Anyone the API describes by a name and an email address. The name is
 * empty until they give one (null only where the person may be missing,
 * e.g. an invitation's sender). */
export interface Person {
  name: string | null
  email: string
}

/** How a person is shown: their name, or their email address while they
 * haven't given one. */
export function displayName({ name, email }: Person) {
  return name || email
}

/** Who created a project or document, as `displayName` shows them. */
export function creatorName(resource: { created_by_name: string; created_by_email: string }) {
  return displayName({ name: resource.created_by_name, email: resource.created_by_email })
}
