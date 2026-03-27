"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLanguage } from "@/components/shared/LanguageProvider";
import { Home, ShoppingBag, Repeat, PlusCircle, User } from "lucide-react";

export default function BottomNav() {
  const { t } = useLanguage();
  const pathname = usePathname();

  const links = [
    { href: "/", icon: Home, label: t("home") },
    { href: "/rent", icon: Repeat, label: t("rent") },
    { href: "/list", icon: PlusCircle, label: t("list") },
    { href: "/buy", icon: ShoppingBag, label: t("buy") },
    { href: "/dashboard", icon: User, label: t("dashboard") },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 glass border-t border-dark-border">
      <div className="flex items-center justify-around py-2">
        {links.map((link) => {
          const isActive =
            link.href === "/"
              ? pathname === "/"
              : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex flex-col items-center gap-0.5 py-1 px-3 rounded-lg transition-colors ${
                isActive
                  ? "text-fashion-gold"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              <link.icon className="w-5 h-5" />
              <span className="text-[10px] font-medium">{link.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
