import type { ReactNode } from 'react'

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

interface AuthCardProps {
  title: string
  description?: ReactNode
  footer?: ReactNode
  children?: ReactNode
}

export function AuthCard({ title, description, footer, children }: AuthCardProps) {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-4">
      <p className="text-lg font-semibold tracking-tight">DocSphere</p>
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>
            <h1>{title}</h1>
          </CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        {children && <CardContent>{children}</CardContent>}
        {footer && (
          <CardFooter className="justify-center text-sm text-muted-foreground">{footer}</CardFooter>
        )}
      </Card>
    </main>
  )
}
