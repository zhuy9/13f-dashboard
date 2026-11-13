import { Component, type ReactNode } from 'react'
import { ErrorState } from '@/components/AsyncStates'

interface State {
  message: string | null
}

// Firestore documents are read as their TypeScript type without a runtime check, so a document
// with an unexpected shape throws while rendering. Uncaught, that unmounts the whole app to a
// blank page. Here the header and footer stay, and the page says what went wrong.
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { message: null }

  static getDerivedStateFromError(error: unknown): State {
    return { message: error instanceof Error ? error.message : 'Unknown error' }
  }

  render(): ReactNode {
    if (this.state.message === null) return this.props.children
    return <ErrorState message={`This page could not be displayed (${this.state.message}). Reload, or open another page.`} />
  }
}
