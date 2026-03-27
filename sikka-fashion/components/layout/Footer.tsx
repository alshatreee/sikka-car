"use client";

import Link from "next/link";
import { useLanguage } from "@/components/shared/LanguageProvider";
import { Crown } from "lucide-react";

export default function Footer() {
  const { t, isRTL } = useLanguage();

  return (
    <footer className="bg-dark-card border-t border-dark-border mt-16 pb-20 md:pb-0">
      <div className="max-w-7xl mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Crown className="w-6 h-6 text-fashion-gold" />
              <span className="text-lg font-bold gradient-text">
                {isRTL ? "خزانة" : "Khizana"}
              </span>
            </div>
            <p className="text-text-muted text-sm leading-relaxed">
              {t("footerTagline")}
            </p>
          </div>

          {/* Links */}
          <div>
            <h3 className="text-text-primary font-semibold mb-3">
              {isRTL ? "روابط سريعة" : "Quick Links"}
            </h3>
            <div className="flex flex-col gap-2">
              <Link
                href="/rent"
                className="text-text-muted hover:text-fashion-gold text-sm transition-colors"
              >
                {t("footerRent")}
              </Link>
              <Link
                href="/buy"
                className="text-text-muted hover:text-fashion-gold text-sm transition-colors"
              >
                {t("footerBuy")}
              </Link>
              <Link
                href="/list"
                className="text-text-muted hover:text-fashion-gold text-sm transition-colors"
              >
                {t("list")}
              </Link>
            </div>
          </div>

          {/* Contact */}
          <div>
            <h3 className="text-text-primary font-semibold mb-3">
              {t("footerContact")}
            </h3>
            <p className="text-text-muted text-sm">info@khizana.kw</p>
            <p className="text-text-muted text-sm mt-1">+965 XXXX XXXX</p>
          </div>
        </div>

        <div className="border-t border-dark-border mt-8 pt-6 text-center">
          <p className="text-text-muted text-xs">
            © 2026 {isRTL ? "خزانة" : "Khizana"}. {t("footerRights")}.
          </p>
        </div>
      </div>
    </footer>
  );
}
