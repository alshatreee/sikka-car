'use server'

import { getOrCreateCurrentUser } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { revalidatePath } from 'next/cache'

export async function sendMessage(
  receiverId: string,
  content: string,
  bookingId?: string
) {
  const user = await getOrCreateCurrentUser()
  if (!user) {
    throw new Error('غير مصرح لك بالوصول')
  }

  if (!content.trim()) {
    throw new Error('الرسالة لا يمكن أن تكون فارغة')
  }

  const message = await prisma.message.create({
    data: {
      senderId: user.id,
      receiverId,
      content: content.trim(),
      bookingId: bookingId || null,
    },
    include: {
      sender: true,
      receiver: true,
    },
  })

  revalidatePath('/messages')
  return message
}

export async function getConversations() {
  const user = await getOrCreateCurrentUser()
  if (!user) {
    throw new Error('غير مصرح لك بالوصول')
  }

  // Get all unique users we have messages with (both sent and received)
  const sentMessages = await prisma.message.findMany({
    where: { senderId: user.id },
    distinct: ['receiverId'],
    orderBy: { createdAt: 'desc' },
    select: { receiverId: true },
  })

  const receivedMessages = await prisma.message.findMany({
    where: { receiverId: user.id },
    distinct: ['senderId'],
    orderBy: { createdAt: 'desc' },
    select: { senderId: true },
  })

  const userIds = Array.from(
    new Set([
      ...sentMessages.map((m) => m.receiverId),
      ...receivedMessages.map((m) => m.senderId),
    ])
  )

  // Get conversations with last message for each user
  const conversations = await Promise.all(
    userIds.map(async (userId) => {
      const lastMessage = await prisma.message.findFirst({
        where: {
          OR: [
            { senderId: user.id, receiverId: userId },
            { senderId: userId, receiverId: user.id },
          ],
        },
        orderBy: { createdAt: 'desc' },
        include: {
          sender: true,
          receiver: true,
        },
      })

      const unreadCount = await prisma.message.count({
        where: {
          senderId: userId,
          receiverId: user.id,
          read: false,
        },
      })

      return {
        otherUserId: userId,
        otherUser: lastMessage?.sender.id === user.id ? lastMessage.receiver : lastMessage?.sender,
        lastMessage,
        unreadCount,
      }
    })
  )

  // Sort by last message date
  return conversations
    .filter((c) => c.lastMessage)
    .sort((a, b) => {
      if (!a.lastMessage || !b.lastMessage) return 0
      return (
        new Date(b.lastMessage.createdAt).getTime() -
        new Date(a.lastMessage.createdAt).getTime()
      )
    })
}

export async function getMessages(otherUserId: string) {
  const user = await getOrCreateCurrentUser()
  if (!user) {
    throw new Error('غير مصرح لك بالوصول')
  }

  const messages = await prisma.message.findMany({
    where: {
      OR: [
        { senderId: user.id, receiverId: otherUserId },
        { senderId: otherUserId, receiverId: user.id },
      ],
    },
    orderBy: { createdAt: 'asc' },
    include: {
      sender: true,
      receiver: true,
      booking: {
        select: {
          id: true,
          startDate: true,
          endDate: true,
          car: {
            select: {
              title: true,
              titleEn: true,
            },
          },
        },
      },
    },
  })

  return messages
}

export async function markAsRead(otherUserId: string) {
  const user = await getOrCreateCurrentUser()
  if (!user) {
    throw new Error('غير مصرح لك بالوصول')
  }

  await prisma.message.updateMany({
    where: {
      senderId: otherUserId,
      receiverId: user.id,
      read: false,
    },
    data: { read: true },
  })

  revalidatePath('/messages')
}

export async function getUnreadCount() {
  const user = await getOrCreateCurrentUser()
  if (!user) {
    return 0
  }

  const count = await prisma.message.count({
    where: {
      receiverId: user.id,
      read: false,
    },
  })

  return count
}
