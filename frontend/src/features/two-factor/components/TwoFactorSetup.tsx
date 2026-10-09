import { zodResolver } from '@hookform/resolvers/zod'
import { QRCodeSVG } from 'qrcode.react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import type { TwoFactorSetup as TwoFactorKey } from '@/api/types'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { RecoveryCodesList } from '@/features/two-factor/components/RecoveryCodesList'
import { useConfirmTwoFactor, useStartTwoFactorSetup } from '@/features/two-factor/hooks'
import { APP_CODE_DIGITS, appCodeSchema } from '@/features/two-factor/schemas'
import { applyApiErrors } from '@/lib/form-errors'

const QR_CODE_SIZE = 176
// The key is easier to type in from groups of four characters.
const KEY_GROUP = /.{1,4}/g

type ConfirmMutation = ReturnType<typeof useConfirmTwoFactor>

/** Setting up two-factor sign-in, a step at a time: what it takes, then a new
 * key for the authenticator app (a QR code, or the key to type in) and a code
 * from the app to confirm it, then the recovery codes - shown only here.
 * `onDone` runs once they've been saved. */
export function TwoFactorSetup({ onDone }: { onDone: () => void }) {
  const start = useStartTwoFactorSetup()
  const confirm = useConfirmTwoFactor()

  if (confirm.data) {
    return <SaveRecoveryCodes codes={confirm.data.recovery_codes} onDone={onDone} />
  }
  if (start.data) {
    return <ScanKey setup={start.data} confirm={confirm} />
  }

  const getStarted = () =>
    start.mutate(undefined, {
      onError: (error) =>
        toast.error(actionErrorMessage(error, "Couldn't start setting up two-factor sign-in.")),
    })

  return (
    <div className="flex flex-col gap-4 text-sm">
      <p className="text-muted-foreground">
        You&apos;ll need an authenticator app on your phone, such as Google Authenticator, Microsoft
        Authenticator or 1Password. Each time you log in, you&apos;ll enter the {APP_CODE_DIGITS}
        -digit code it shows as well as your password.
      </p>
      <Button className="self-start" disabled={start.isPending} onClick={getStarted}>
        {start.isPending && <Spinner aria-hidden />}
        Get started
      </Button>
    </div>
  )
}

function ScanKey({ setup, confirm }: { setup: TwoFactorKey; confirm: ConfirmMutation }) {
  const form = useForm({ resolver: zodResolver(appCodeSchema), defaultValues: { otp: '' } })
  const { errors } = form.formState

  const onSubmit = form.handleSubmit((values) =>
    confirm.mutate(values, {
      onSuccess: () => toast.success('Two-factor sign-in is on.'),
      onError: (error) => applyApiErrors(error, form),
    }),
  )

  return (
    <div className="flex flex-col gap-4 text-sm">
      <p className="text-muted-foreground">
        Scan this QR code with your authenticator app, then enter the code it shows.
      </p>
      <QRCodeSVG
        value={setup.otpauth_uri}
        size={QR_CODE_SIZE}
        marginSize={2}
        bgColor="#ffffff"
        fgColor="#000000"
        title="QR code for your authenticator app"
        className="self-center rounded-md"
      />
      <p className="text-muted-foreground">
        Can&apos;t scan it? Enter this key instead:{' '}
        <code className="font-mono break-all text-foreground">
          {setup.secret.match(KEY_GROUP)?.join(' ')}
        </code>
      </p>
      <form
        onSubmit={onSubmit}
        noValidate
        aria-label="Confirm two-factor sign-in"
        className="flex flex-col gap-4"
      >
        <FormAlert message={errors.root?.server?.message} />
        <TextField
          label="Code from your app"
          inputMode="numeric"
          autoComplete="one-time-code"
          error={errors.otp?.message}
          {...form.register('otp')}
        />
        <SubmitButton isPending={confirm.isPending} className="self-start">
          Turn on
        </SubmitButton>
      </form>
    </div>
  )
}

function SaveRecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  return (
    <div className="flex flex-col gap-4 text-sm">
      <p className="text-muted-foreground">
        Two-factor sign-in is on. Save these recovery codes somewhere safe: if you lose your phone,
        each one logs you in once instead of a code from the app. They won&apos;t be shown again.
      </p>
      <RecoveryCodesList codes={codes} />
      <Button className="self-start" onClick={onDone}>
        I&apos;ve saved them
      </Button>
    </div>
  )
}
