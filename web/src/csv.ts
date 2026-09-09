export function csv(rows: object[], context: object): string {
  const records = rows.map(row => ({ ...row, ...context }))
  const columns = [...new Set(records.flatMap(row => Object.keys(row)))]
  const cell = (value: unknown) => {
    let text = value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value)
    if (typeof value === 'string' && /^[\s]*[=+@-]|^[\t\r\n]/.test(text)) text = `'${text}`
    return `"${text.replaceAll('"', '""')}"`
  }
  return [columns.map(cell).join(','), ...records.map(row => {
    const values: Record<string, unknown> = row
    return columns.map(key => cell(values[key])).join(',')
  })].join('\r\n')
}
