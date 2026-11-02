import { useEffect, useRef, useState } from "react";

export function OrigoCompanion() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let cancelled = false;
    let dispose: (() => void) | undefined;
    const surface = canvas.current;
    if (!surface) return;
    function lost(event: Event) {
      event.preventDefault();
      cancelled = true;
      dispose?.();
      dispose = undefined;
      setReady(false);
    }
    surface.addEventListener("webglcontextlost", lost);
    import("./origo-companion-scene.js").then(({ mountCompanion }) => {
      if (cancelled) return;
      try {
        dispose = mountCompanion(surface);
        setReady(true);
      } catch { /* Keep the offline fallback when WebGL is unavailable. */ }
    }).catch(() => {});
    return () => { cancelled = true; surface.removeEventListener("webglcontextlost", lost); dispose?.(); };
  }, []);
  return <div className="origo-companion" aria-hidden="true">
    {!ready && <img src="/logo.png" alt="" className="origo-companion-fallback" />}
    <canvas ref={canvas} width={360} height={270} className={ready ? "" : "origo-companion-pending"} />
  </div>;
}
