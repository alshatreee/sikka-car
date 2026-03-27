"use client";

import Link from "next/link";
import { useLanguage } from "@/components/shared/LanguageProvider";
import { Crown, Globe, Menu, X } from "lucide-react";
import { useState } from "react";

export default function Header() {
  const { t, toggleLanguage, language, isRTL } = useLanguage();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="glass sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2">
          <Crown className="w-7 h-7 text-fashion-gold" />
          <span className="text-xl font-bold gradient-text">
            {isRTL ? "خزانة" : "Khizana"}
          </span>
        </Link>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-6">
          <Link
            href="/"
            className="text-text-secondary hover:text-fashion-gold transition-colors text-sm font-medium"
          >
            {t("home")}
          </Link>
          <Link
            href="/rent"
            className="text-text-secondary hover:text-fashion-gold transition-colors text-sm font-medium"
          >
            {t("rent")}
          </Link>
          <Link
            href="/buy"
            className="text-text-secondary hover:text-fashion-gold transition-colors text-sm font-medium"
          >
            {t("buy")}
          </Link>
          <Link
            href="/list"
            className="text-text-secondary hover:text-fashion-gold transition-colors text-sm font-medium"
          >
            {t("list")}
          </Link>
          <Link
            href="/dashboard"
            className="text-text-secondary hover:text-fashion-gold transition-colors text-sm font-medium"
          >
            {t("dashboard")}
          </Link>
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={toggleLanguage}
            className="flex items-center gap-1 text-text-muted hover:text-fashion-gold transition-colors text-sm"
          >
            <Globe className="w-4 h-4" />
            {language === "ar" ? "EN" : "عربي"}
          </button>

          <Link href="/sign-in" className="btn-primary text-sm py-2 px-4">
            {t("login")}
          </Link>

          {/* Mobile menu toggle */}
          <button
            className="md:hidden text-text-secondary"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {menuOpen && (
        <nav className="md:hidden bg-dark-card border-t border-dark-border px-4 py-4 flex flex-col gap-3">
          <Link
            href="/"
            className="text-text-secondary hover:text-fashion-gold transition-colors py-2"
            onClick={() => setMenuOpen(false)}
          >
            {t("home")}
          </Link>
          <Link
            href="/rent"
            className="text-text-secondary hover:text-fashion-gold transition-colors py-2"
            onClick={() => setMenuOpen(false)}
          >
            {t("rent")}
          </Link>
          <Link
            href="/buy"
            className="text-text-secondary hover:text-fashion-gold transition-colors py-2"
            onClick={() => setMenuOpen(false)}
          >
            {t("buy")}
          </Link>
          <Link
            href="/list"
            className="text-text-secondary hover:text-fashion-gold transition-colors py-2"
            onClick={() => setMenuOpen(false)}
          >
            {t("list")}
          </Link>
          <Link
            href="/dashboard"
            className="text-text-secondary hover:text-fashion-gold transition-colors py-2"
            onClick={() => setMenuOpen(false)}
          >
            {t("dashboard")}
          </Link>
        </nav>
      )}
    </header>
  );
}
