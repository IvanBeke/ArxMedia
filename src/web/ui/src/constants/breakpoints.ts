/* Breakpoints, single-sourced: keep in sync with the @theme tokens and
   :root vars in src/assets/main.css. */
export const BREAKPOINTS = Object.freeze({
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
} as const)

/** max-width query matching Tailwind's `max-*` variants (e.g. max-md). */
export function belowBreakpoint(px: number): string {
  return `(max-width: ${px - 1}px)`
}
