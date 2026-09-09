export function required<T>(value: T | null | undefined, description: string): T {
  if (value === null || value === undefined) {
    throw new Error(`${description} was not found`)
  }
  return value
}
