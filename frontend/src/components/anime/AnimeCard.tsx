import { Link } from "react-router-dom";
import { Badge } from "../common/Badge";

interface AnimeCardProps {
  slug: string;
  title: string;
  posterUrl: string | null;
  /** Optional corner badge, e.g. "NEW" - only shown when the caller has a real basis for it. */
  badge?: string;
}

export function AnimeCard({ slug, title, posterUrl, badge }: AnimeCardProps) {
  return (
    <Link to={`/anime/${slug}`} className="anime-card">
      <div className="anime-card-poster">
        {posterUrl ? (
          <img src={posterUrl} alt={title} loading="lazy" />
        ) : (
          <div style={{ aspectRatio: "2 / 3", background: "var(--color-surface-alt)" }} />
        )}
        {badge && (
          <div className="anime-card-badge">
            <Badge variant="accent">{badge}</Badge>
          </div>
        )}
      </div>
      <div className="anime-card-title">{title}</div>
    </Link>
  );
}
