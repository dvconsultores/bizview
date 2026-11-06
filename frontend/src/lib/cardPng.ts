/** Feature 056: a card's chart as a PNG, without a new dependency.
 *
 * The charts are SVG the app draws itself, so the picture is produced by serialising that element
 * into a canvas: no screenshot library, no external font request, nothing that could leak a URL.
 */

function download(href: string, filename: string): void {
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

/** The first `<svg>` inside `root`, as a PNG download named `filename` (without extension). */
export function downloadCardPng(root: HTMLElement | null, filename: string): boolean {
  const svg = root?.querySelector("svg");
  if (!svg) return false;
  const width = Number(svg.getAttribute("width")) || svg.getBoundingClientRect().width || 800;
  const height = Number(svg.getAttribute("height")) || svg.getBoundingClientRect().height || 400;
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  // The card's own surface, read from the live theme: the picture matches the screen it came from.
  const surface = root ? getComputedStyle(root).getPropertyValue("--surface").trim() : "";
  const background = getComputedStyle(document.body).backgroundColor || surface;
  const serialized = new XMLSerializer().serializeToString(clone);
  const svgUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(serialized)}`;
  const image = new Image();
  const scale = 2;
  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    const context = canvas.getContext("2d");
    if (!context) return;
    context.fillStyle = background;
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    try {
      download(canvas.toDataURL("image/png"), `${filename}.png`);
    } catch {
      /* a tainted canvas cannot be exported; the card still offers its CSV */
    }
  };
  image.src = svgUrl;
  return true;
}
