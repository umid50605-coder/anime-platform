import type { ReactNode } from "react";

interface HeroProps {
  eyebrow?: string;
  title: string;
  subtitle: string;
  backgroundImage?: string | null;
  children?: ReactNode;
}

export function Hero({ eyebrow, title, subtitle, backgroundImage, children }: HeroProps) {
  return (
    <section className="hero">
      {backgroundImage && (
        <div className="hero-backdrop" style={{ backgroundImage: `url(${backgroundImage})` }} />
      )}
      <div className="hero-scrim" />
      <div className="hero-content fade-in">
        {eyebrow && <div className="hero-eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{subtitle}</p>
        {children}
      </div>
    </section>
  );
}
