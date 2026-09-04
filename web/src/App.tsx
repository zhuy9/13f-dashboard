import { Navigate, Route, Routes } from 'react-router-dom'
import { Footer } from '@/components/Footer'
import { Header } from '@/components/Header'
import { MetaProvider } from '@/context/MetaContext'
import { InvestorPage } from '@/pages/InvestorPage'
import { ManagerPage } from '@/pages/ManagerPage'
import { ManagersPage } from '@/pages/ManagersPage'
import { OwnershipPage } from '@/pages/OwnershipPage'
import { PatternsPage } from '@/pages/PatternsPage'
import { StockPage } from '@/pages/StockPage'

export function App() {
  return (
    <MetaProvider>
      <Header />
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/patterns" replace />} />
          <Route path="/patterns" element={<PatternsPage />} />
          <Route path="/managers" element={<ManagersPage />} />
          <Route path="/manager/:cik" element={<ManagerPage />} />
          <Route path="/stock/:symbol" element={<StockPage />} />
          <Route path="/ownership" element={<OwnershipPage />} />
          <Route path="/investor/:cik" element={<InvestorPage />} />
        </Routes>
      </main>
      <Footer />
    </MetaProvider>
  )
}
