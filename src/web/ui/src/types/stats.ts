export interface StatColumnSegment {
  value: number
  barClass: string
}

export interface StatColumnItem {
  key: string
  label: string
  value: number
  display?: string
  title?: string
  /** Stacked parts, bottom first; `value` must be their total. */
  segments?: StatColumnSegment[]
}

/** One part of a whole, as drawn by the pie and the stacked bar. */
export interface StatSliceInput {
  key: string
  label: string
  value: number
  /** A `text-*` class; the slice and its legend dot draw in the current text colour. */
  colorClass: string
  display?: string
}

export interface StatSlice extends StatSliceInput {
  /** Share of the total, 0-100, unrounded. */
  share: number
  /** Where the slice starts, as the summed share of the slices before it. */
  offset: number
  /** Rounded share; the rounded shares of all slices add up to 100. */
  percent: number
}
