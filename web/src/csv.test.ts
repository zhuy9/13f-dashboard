import { expect, it } from 'vitest'
import { csv } from './csv'

it('exports all rows, provenance, nested details and safely quoted spreadsheet text', () => {
  const out = csv([{ name: '=1+1', amount: -2, detail: 'a,"b"\nc' }, { name: '\t@SUM(A1)', holders: ['M1'] }],
    { period: '2026-03-31', accessions: ['filing-1'], methodologyVersion: 2 })
  expect(out).toContain('"\'=1+1","-2","a,""b""\nc"')
  expect(out).toContain('"\'\t@SUM(A1)"')
  expect(out.match(/2026-03-31/g)).toHaveLength(2)
  expect(out).toContain('"[""filing-1""]"')
  expect(out).toContain('"[""M1""]"')
})
