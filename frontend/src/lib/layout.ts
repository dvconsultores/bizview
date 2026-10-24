/** The app's content container (feature 030 FR-001): one definition shared by the authenticated
 * shell and the public pages, so the report page and the shared view span the same width as
 * Tableros and Administración instead of a narrower centred column. */
export const APP_CONTAINER = "mx-auto w-full max-w-screen-2xl";

/** Phone-first gutters: 16 px at 375 px, the reference app's 20 px from 640 px, 16 px on desktop. */
export const APP_GUTTER = "px-4 sm:px-5 lg:px-4";

export const APP_PAGE = `${APP_CONTAINER} ${APP_GUTTER}`;
