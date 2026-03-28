import { notFound, redirect } from 'next/navigation'
import { auth } from '@clerk/nextjs/server'
import { prisma } from '@/lib/prisma'
import Link from 'next/link'
import { ArrowLeft, Printer } from 'lucide-react'
import { RentalContract } from '@/components/legal/RentalContract'

interface ContractPageProps {
  params: Promise<{
    bookingId: string
  }>
}

export default async function ContractPage({ params }: ContractPageProps) {
  const { userId } = await auth()

  if (!userId) {
    redirect('/sign-in')
  }

  const { bookingId } = await params

  // Get the current user from the database
  const currentUser = await prisma.user.findUnique({
    where: { clerkUserId: userId },
    select: { id: true },
  })

  if (!currentUser) {
    redirect('/sign-in')
  }

  // Fetch the booking with all necessary relations
  const booking = await prisma.booking.findUnique({
    where: { id: bookingId },
    include: {
      car: {
        include: {
          owner: {
            select: {
              fullName: true,
              phone: true,
            },
          },
        },
      },
      renter: {
        select: {
          id: true,
          fullName: true,
          email: true,
          phone: true,
        },
      },
    },
  })

  if (!booking) {
    notFound()
  }

  // Check if the current user is either the renter or the owner of the car
  const isRenter = booking.renterId === currentUser.id
  const isOwner = booking.car.ownerId === currentUser.id

  if (!isRenter && !isOwner) {
    notFound()
  }

  return (
    <div className="min-h-screen bg-dark-bg" dir="auto">
      {/* Header with Print Button */}
      <div className="sticky top-0 z-10 border-b border-dark-border bg-dark-card px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 rounded-lg border border-dark-border px-3 py-2 text-sm text-text-secondary transition-all hover:bg-dark-surface print:hidden"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="hidden sm:inline">العودة / Back</span>
          </Link>

          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 rounded-lg border border-dark-border bg-brand-solid px-3 py-2 text-sm font-medium text-text-primary transition-all hover:bg-brand-solid-hover print:hidden"
          >
            <Printer className="h-4 w-4" />
            <span>طباعة العقد / Print Contract</span>
          </button>
        </div>
      </div>

      {/* Contract Content */}
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 print:max-w-full print:p-0">
        <div className="rounded-lg border border-dark-border bg-dark-card p-8 print:border-none print:bg-white print:p-0 print:shadow-none">
          <RentalContract
            booking={{
              id: booking.id,
              startDate: booking.startDate,
              endDate: booking.endDate,
              totalDays: booking.totalDays,
              totalAmount: String(booking.totalAmount),
              notes: booking.notes,
              car: {
                title: booking.car.title,
                year: booking.car.year,
                category: booking.car.category,
                area: booking.car.area,
                dailyPrice: String(booking.car.dailyPrice),
              },
              renter: {
                fullName: booking.renter.fullName,
                email: booking.renter.email,
                phone: booking.renter.phone,
              },
            }}
            owner={{
              fullName: booking.car.owner.fullName,
              phone: booking.car.owner.phone,
            }}
          />
        </div>
      </div>

      {/* Print Styles */}
      <style>{`
        @media print {
          body {
            background: white;
            margin: 0;
            padding: 0;
          }
          .print\\:hidden {
            display: none !important;
          }
          .print\\:max-w-full {
            max-width: 100%;
          }
          .print\\:p-0 {
            padding: 0;
          }
          .print\\:border-none {
            border: none;
          }
          .print\\:bg-white {
            background: white;
          }
          .print\\:shadow-none {
            box-shadow: none;
          }
        }
      `}</style>
    </div>
  )
}
