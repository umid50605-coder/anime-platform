import { useEffect, useRef } from "react";

interface VideoPlayerProps {
  src: string;
  startPositionSeconds: number;
  onProgress: (positionSeconds: number) => void;
}

/**
 * Intentionally basic: a native <video> element with a resume point and a
 * periodic progress callback. No adaptive bitrate, bandwidth estimation, or
 * prefetching - see ARCHITECTURE.md "What is intentionally not implemented".
 * Visual framing (rounded shell, 16:9, background) lives in
 * VideoPlayerContainer, not here - this component only owns playback logic.
 */
export function VideoPlayer({ src, startPositionSeconds, onProgress }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hasSeekedRef = useRef(false);

  useEffect(() => {
    hasSeekedRef.current = false;
  }, [src]);

  return (
    <video
      ref={videoRef}
      src={src}
      controls
      onLoadedMetadata={() => {
        const video = videoRef.current;
        if (video && !hasSeekedRef.current && startPositionSeconds > 0) {
          video.currentTime = startPositionSeconds;
          hasSeekedRef.current = true;
        }
      }}
      onTimeUpdate={(e) => {
        // Simple periodic reporting via the browser's native timeupdate event
        // (fires a few times a second) - no custom polling/interval needed.
        onProgress(Math.floor(e.currentTarget.currentTime));
      }}
      onPause={(e) => onProgress(Math.floor(e.currentTarget.currentTime))}
    />
  );
}
