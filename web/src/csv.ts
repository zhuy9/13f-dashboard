/** One CSV, with `context` appended to every row as trailing provenance columns.
 *
 * `context` values that are undefined are dropped rather than written as an empty column, so a
 * table with no manager threshold does not ship a `minimumManagers` column full of nothing.
 */
export function csv(rows: object[], context: object): string {
  const provenance = Object.entries(context).filter(([, value]) => value !== undefined)
  const trailing = provenance.map(([key]) => key)
  const records: Record<string, unknown>[] = rows.map(row => ({ ...row, ...Object.fromEntries(provenance) }))
  // Sorted, not first-seen. Rows of one table do not all carry the same fields -- a NEW position
  // has no prevWeight, prevShares or change -- so first-seen order made the column layout depend
  // on which row happened to sort first, and the same table exported twice could differ.
  const data = [...new Set(records.flatMap(row => Object.keys(row)))]
    .filter(key => !trailing.includes(key))
    .sort()
  const columns = [...data, ...trailing]
  const cell = (value: unknown) => {
    let text = value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value)
    if (typeof value === 'string' && /^\s*[=+@-]|^[\t\r\n]/.test(text)) text = `'${text}`
    return `"${text.replaceAll('"', '""')}"`
  }
  const line = (row: Record<string, unknown>) => columns.map(key => cell(row[key])).join(',')
  return [columns.map(cell).join(','), ...records.map(line)].join('\r\n')
}
