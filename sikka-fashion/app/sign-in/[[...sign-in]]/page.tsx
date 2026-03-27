import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <SignIn
        appearance={{
          elements: {
            rootBox: "mx-auto",
            card: "bg-dark-card border border-dark-border shadow-xl",
            headerTitle: "text-text-primary",
            headerSubtitle: "text-text-muted",
            socialButtonsBlockButton:
              "bg-dark-surface border-dark-border text-text-primary hover:bg-dark-border",
            formFieldLabel: "text-text-secondary",
            formFieldInput:
              "bg-dark-surface border-dark-border text-text-primary",
            footerActionLink: "text-fashion-gold hover:text-fashion-gold-light",
            formButtonPrimary:
              "bg-fashion-gold hover:bg-fashion-gold-dark text-dark-bg",
          },
        }}
      />
    </div>
  );
}
