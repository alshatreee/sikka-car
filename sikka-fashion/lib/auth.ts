import { auth, currentUser } from "@clerk/nextjs/server";
import { prisma } from "./prisma";

export async function getOrCreateCurrentUser() {
  const { userId } = await auth();
  if (!userId) return null;

  let user = await prisma.user.findUnique({
    where: { clerkUserId: userId },
  });

  if (!user) {
    const clerkUser = await currentUser();
    if (!clerkUser) return null;

    user = await prisma.user.create({
      data: {
        clerkUserId: userId,
        email: clerkUser.emailAddresses[0]?.emailAddress || "",
        fullName: `${clerkUser.firstName || ""} ${clerkUser.lastName || ""}`.trim(),
        phone: clerkUser.phoneNumbers[0]?.phoneNumber || null,
        avatarUrl: clerkUser.imageUrl || null,
      },
    });
  }

  return user;
}

export async function requireAdmin() {
  const user = await getOrCreateCurrentUser();
  if (!user || user.role !== "ADMIN") {
    throw new Error("Unauthorized: Admin access required");
  }
  return user;
}

export async function isAdmin(): Promise<boolean> {
  const user = await getOrCreateCurrentUser();
  return user?.role === "ADMIN";
}
