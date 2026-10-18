const KEY = "bizview.nav";

/** The left menu, collapsed to an icon rail or expanded (feature 025). A device choice, like the
 * theme: it is remembered per browser, not on the account. */
export function readNavCollapsed(): boolean {
  try {
    return localStorage.getItem(KEY) === "collapsed";
  } catch {
    return false;
  }
}

export function writeNavCollapsed(collapsed: boolean): void {
  try {
    if (collapsed) localStorage.setItem(KEY, "collapsed");
    else localStorage.removeItem(KEY);
  } catch {
    // storage blocked: the choice still applies for this session
  }
}
