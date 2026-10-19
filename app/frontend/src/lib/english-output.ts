/** Presentation only. Original requests and source documents remain unchanged. */
export function englishDisplay(value: string): string {
  return value.replace(
    /[\u3400-\u9fff\uf900-\ufaff]+/g,
    '[Non-English text; inspect original]'
  )
}
