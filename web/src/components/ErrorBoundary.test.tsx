import type { ReactElement } from 'react'
import { expect, it } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'

it('shows the error in place of the page that threw', () => {
  const boundary = new ErrorBoundary({ children: 'page' })
  expect(boundary.render()).toBe('page')

  boundary.state = ErrorBoundary.getDerivedStateFromError(new Error('holders is undefined'))

  const shown = boundary.render() as ReactElement<{ message: string }>
  expect(shown.props.message).toContain('holders is undefined')
})
