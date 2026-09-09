export function csv(rows: object[], context: object): string {
  const records: Record<string, unknown>[] = rows.map(row => ({ ...row, ...context }))
  const columns = [...new Set(records.flatMap(row => Object.keys(row)))]
  const cell = (value: unknown) => {
    let text = value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value)
    if (typeof value === 'string' && /^\s*[=+@-]|^[\t\r\n]/.test(text)) text = `'${text}`
    return `"${text.replaceAll('"', '""')}"`
  }
  const line = (row: Record<string, unknown>) => columns.map(key => cell(row[key])).join(',')
  return [columns.map(cell).join(','), ...records.map(line)].join('\r\n')
}
