/** Case- and accent-insensitive folding for search fields (feature 025): "Administración"
 * matches "administracion". */
export function fold(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}
