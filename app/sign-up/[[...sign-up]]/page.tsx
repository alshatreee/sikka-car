import { SignUp } from '@clerk/nextjs'

export default function SignUpPage() {
  return (
    <main className="flex min-h-[80vh] items-center justify-center py-12">
      <SignUp
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
