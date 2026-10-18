import { Fragment, type ReactNode } from "react";

/**
 * Splits a catalogue sentence containing `{name}` placeholders and replaces
 * them with inline elements (code chips, links, …). Placeholders keep word
 * order flexible so each language can move inline elements naturally
 * (feature 022).
 */
export function rich(template: string, parts: Record<string, ReactNode>): ReactNode {
  if (!template) return null;
  const pieces: ReactNode[] = [];
  const re = /\{([a-zA-Z][a-zA-Z0-9]*)\}/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(template)) !== null) {
    if (m.index > last) pieces.push(template.slice(last, m.index));
    const name = m[1];
    pieces.push(name in parts ? <Fragment key={i++}>{parts[name]}</Fragment> : `{${name}}`);
    last = m.index + m[0].length;
  }
  if (last < template.length) pieces.push(template.slice(last));
  return <Fragment>{pieces}</Fragment>;
}
