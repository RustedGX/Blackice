import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Portfolio from './pages/Portfolio'
import Backtesting from './pages/Backtesting'
import TradeHistory from './pages/TradeHistory'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="portfolio" element={<Portfolio />} />
          <Route path="backtest" element={<Backtesting />} />
          <Route path="history" element={<TradeHistory />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
