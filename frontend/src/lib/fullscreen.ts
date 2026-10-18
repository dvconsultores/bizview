interface WebkitFullscreenDocument extends Document {
  webkitFullscreenElement?: Element | null;
  webkitExitFullscreen?: () => void;
  webkitCancelFullScreen?: () => void;
}

interface WebkitFullscreenElement extends HTMLElement {
  webkitRequestFullscreen?: () => void;
}

function asWebkitDoc(doc: Document): WebkitFullscreenDocument {
  return doc as unknown as WebkitFullscreenDocument;
}

function asWebkitEl(el: HTMLElement): WebkitFullscreenElement {
  return el as unknown as WebkitFullscreenElement;
}

export function fullscreenSupported(doc: Document = document): boolean {
  const d = asWebkitDoc(doc);
  return Boolean(d.documentElement.requestFullscreen || asWebkitEl(d.documentElement).webkitRequestFullscreen);
}

export function isFullscreen(doc: Document = document): boolean {
  const d = asWebkitDoc(doc);
  return Boolean(d.fullscreenElement || d.webkitFullscreenElement);
}

export function enterFullscreen(el: HTMLElement = document.documentElement): Promise<boolean> {
  const std = el.requestFullscreen;
  if (typeof std === "function") {
    try {
      const result = std.call(el);
      if (result && typeof result.catch === "function") {
        return result.then(
          () => true,
          () => false,
        );
      }
      return Promise.resolve(true);
    } catch {
      return Promise.resolve(false);
    }
  }

  const webkit = asWebkitEl(el).webkitRequestFullscreen;
  if (typeof webkit === "function") {
    try {
      webkit.call(el);
      return Promise.resolve(true);
    } catch {
      return Promise.resolve(false);
    }
  }

  return Promise.resolve(false);
}

export function exitFullscreen(doc: Document = document): Promise<void> {
  if (!isFullscreen(doc)) return Promise.resolve();

  const d = asWebkitDoc(doc);
  if (typeof d.exitFullscreen === "function") {
    try {
      const result = d.exitFullscreen.call(doc);
      if (result && typeof result.catch === "function") {
        return result.catch(() => undefined);
      }
    } catch {
      // swallow
    }
    return Promise.resolve();
  }

  const exit = d.webkitExitFullscreen ?? d.webkitCancelFullScreen;
  if (typeof exit === "function") {
    try {
      exit.call(doc);
    } catch {
      // swallow
    }
  }

  return Promise.resolve();
}

export function onFullscreenChange(cb: () => void, doc: Document = document): () => void {
  doc.addEventListener("fullscreenchange", cb);
  doc.addEventListener("webkitfullscreenchange", cb);
  return () => {
    doc.removeEventListener("fullscreenchange", cb);
    doc.removeEventListener("webkitfullscreenchange", cb);
  };
}
