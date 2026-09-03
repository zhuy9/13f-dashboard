import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Missing #root element')
const root = createRoot(rootElement)

// Dynamic import so a config error thrown at module-eval time (e.g. firebase.ts's
// missing-env-var check) rejects this promise instead of crashing before React ever renders.
import('./App')
  .then(({ App }) => {
    root.render(
      <StrictMode>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </StrictMode>,
    )
  })
  .catch((error: unknown) => {
    const message = error instanceof Error ? error.message : 'Failed to start the app.'
    root.render(
      <div style={{ padding: 24, fontFamily: 'sans-serif', color: '#cf222e' }}>
        <h1>Configuration error</h1>
        <p>{message}</p>
      </div>,
    )
  })
