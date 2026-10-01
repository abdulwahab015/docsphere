import { ArrowRightIcon } from 'lucide-react'
import { Link } from 'react-router'

import { PATHS } from '@/app/paths'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { useSignedInMember } from '@/features/auth/hooks'

// A starting point until projects and documents land; then this page will
// show recent work instead.
export function HomePage() {
  const user = useSignedInMember()

  return (
    <>
      <PageHeader title="Home" description={`Signed in as ${user.email}`} />
      <Card className="max-w-md">
        <CardHeader>
          <CardTitle>
            <h2>{user.organization.name}</h2>
          </CardTitle>
          <CardDescription>
            See who&apos;s in your organization before sharing projects and documents.
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <Button asChild variant="outline">
            <Link to={PATHS.people}>
              View people
              <ArrowRightIcon aria-hidden />
            </Link>
          </Button>
        </CardFooter>
      </Card>
    </>
  )
}
