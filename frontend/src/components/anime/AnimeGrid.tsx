import { AnimeCard } from "./AnimeCard";

export interface AnimeGridItem {
  key: string;
  slug: string;
  title: string;
  posterUrl: string | null;
  badge?: string;
}

export function AnimeGrid({ items }: { items: AnimeGridItem[] }) {
  return (
    <div className="anime-grid">
      {items.map((item) => (
        <AnimeCard
          key={item.key}
          slug={item.slug}
          title={item.title}
          posterUrl={item.posterUrl}
          badge={item.badge}
        />
      ))}
    </div>
  );
}
