import { SignIn } from '@clerk/nextjs'

export default function SignInPage() {
  return (
    <main className="flex min-h-[80vh] items-center justify-center py-12">
      <SignIn
        appearance={{
          elements: {
            rootBox: 'mx-auto',
            card: 'shadow-xl rounded-2xl',
          },
        }}
      />
    </main>
  )
}
