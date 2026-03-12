/**
 * Convert 2-letter ISO country code to flag emoji.
 * Returns the raw code string for non-2-letter inputs.
 */
export function countryFlag(code: string | null): string {
  if (!code || code.length !== 2) return code || ''
  return code.toUpperCase().replace(/./g, c => String.fromCodePoint(c.charCodeAt(0) + 0x1F1A5))
}
