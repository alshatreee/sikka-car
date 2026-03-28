'use server'

import { prisma } from '@/lib/prisma'

export async function logAudit(params: {
  userId?: string
  action: string
  entity: string
  entityId?: string
  details?: string
  ipAddress?: string
}) {
  try {
    await prisma.auditLog.create({
      data: {
        userId: params.userId,
        action: params.action,
        entity: params.entity,
        entityId: params.entityId,
        details: params.details,
        ipAddress: params.ipAddress,
      },
    })
  } catch (error) {
    console.error('Failed to log audit:', error)
    throw error
  }
}
