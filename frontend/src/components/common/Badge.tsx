import type { ReactNode } from "react";

interface BadgeProps {
  children: ReactNode;
  variant?: "default" | "accent" | "secondary";
}

export function Badge({ children, variant = "default" }: BadgeProps) {
  const variantClass =
    variant === "accent" ? "badge-accent" : variant === "secondary" ? "badge-secondary" : "";
  return <span className={`badge ${variantClass}`.trim()}>{children}</span>;
}
