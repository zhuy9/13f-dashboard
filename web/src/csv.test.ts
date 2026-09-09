import { expect, it } from 'vitest'
import { csv } from './csv'

const header = (out: string) => out.split('\r\n')[0]
const rowsOf = (out: string) => out.split('\r\n').slice(1)

it('exports all rows, provenance, nested details and safely quoted spreadsheet text', () => {
  const out = csv([{ name: '=1+1', amount: -2, detail: 'a,"b"\nc' }, { name: '\t@SUM(A1)', holders: ['M1'] }],
    { period: '2026-03-31', accessions: ['filing-1'], methodologyVersion: 2 })
  expect(out).toContain('"\'=1+1"')
  expect(out).toContain('"\'\t@SUM(A1)"')
  expect(out).toContain('"a,""b""\nc"')
  expect(out.match(/2026-03-31/g)).toHaveLength(2)
  expect(out).toContain('"[""filing-1""]"')
  expect(out).toContain('"[""M1""]"')
})

// A NEW position carries no prevWeight, so first-seen column order made the layout depend on
// which row sorted first: the same table could export two different shapes.
it('orders columns the same way whichever row is missing fields', () => {
  const complete = { symbol: 'AAA', weight: 2, prevWeight: 1 }
  const partial = { symbol: 'BBB', weight: 3 }
  const context = { period: '2026-06-30' }

  const completeFirst = csv([complete, partial], context)
  const partialFirst = csv([partial, complete], context)

  expect(header(completeFirst)).toBe(header(partialFirst))
  expect(header(completeFirst)).toBe('"prevWeight","symbol","weight","period"')
})

it('keeps provenance in the trailing columns, in the order given', () => {
  const out = csv([{ symbol: 'AAA' }], { period: '2026-06-30', managersFiled: 34, methodologyVersion: 2 })

  expect(header(out)).toBe('"symbol","period","managersFiled","methodologyVersion"')
})

// minimum is undefined for a positions or holders export; an always-empty column is noise.
it('drops provenance that has no value rather than exporting an empty column', () => {
  const out = csv([{ symbol: 'AAA' }], { period: '2026-06-30', minimumManagers: undefined })

  expect(header(out)).toBe('"symbol","period"')
  expect(rowsOf(out)).toEqual(['"AAA","2026-06-30"'])
})
