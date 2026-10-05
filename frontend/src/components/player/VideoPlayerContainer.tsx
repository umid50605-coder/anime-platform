import type { ReactNode } from "react";

export function VideoPlayerContainer({ children }: { children: ReactNode }) {
  return <div className="player-shell">{children}</div>;
}
