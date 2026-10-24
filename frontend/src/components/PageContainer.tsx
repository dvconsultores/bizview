import type { HTMLAttributes, ReactNode } from "react";
import { APP_CONTAINER, APP_GUTTER } from "../lib/layout";

interface PageContainerProps extends HTMLAttributes<HTMLElement> {
  as?: "div" | "main" | "header";
  children: ReactNode;
}

/** The app standard container (feature 030 FR-001): max width and gutters come from
 * `lib/layout.ts`, never from a page. Used by the shell's `<main>` and by the public pages that
 * live outside it (the shared view). */
export function PageContainer({ as: Tag = "div", className, children, ...rest }: PageContainerProps) {
  return (
    <Tag className={`${APP_CONTAINER} ${APP_GUTTER}${className ? ` ${className}` : ""}`} {...rest}>
      {children}
    </Tag>
  );
}
