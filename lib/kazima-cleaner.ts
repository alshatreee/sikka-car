// lib/kazima-cleaner.ts
// Arabic text normalization and cleaning for manuscript processing

/**
 * Remove Arabic diacritics (tashkeel)
 * ًٌٍَُِّْـ
 */
export function removeDiacritics(text: string): string {
  return text.replace(/[\u064B-\u065F\u0670\u0640]/g, '')
}

/**
 * Normalize Arabic characters for search matching:
 * - إأآا → ا (alef variants)
 * - ى → ي (alef maqsura)
 *
 * NOTE: ة (ta marbuta) is NOT normalized to ه because
 * they are semantically different. Converting ة→ه would
 * break words like نهاية→نهايه which is incorrect.
 */
export function normalizeArabic(text: string): string {
  let result = text
  result = result.replace(/[إأآا]/g, 'ا')
  result = result.replace(/ى/g, 'ي')
  return result
}

/**
 * Collapse multiple whitespace into single space
 */
export function collapseWhitespace(text: string): string {
  return text.replace(/\s+/g, ' ').trim()
}

/**
 * Full cleaning pipeline for search/matching:
 * 1. Remove diacritics
 * 2. Normalize characters
 * 3. Collapse whitespace
 *
 * Note: This is for search indexing, NOT for display.
 * Always preserve the original text for display and scholarly use.
 */
export function cleanForSearch(text: string): string {
  let result = removeDiacritics(text)
  result = normalizeArabic(result)
  result = collapseWhitespace(result)
  return result
}

/**
 * Light cleaning for LLM input:
 * - Collapse whitespace only
 * - Keep diacritics (important for scholarly text)
 * - Keep original character forms
 */
export function cleanForLLM(text: string): string {
  return collapseWhitespace(text)
}
