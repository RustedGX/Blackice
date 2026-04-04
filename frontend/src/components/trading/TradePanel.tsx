import { useState } from 'react'
import { placeOrder } from '../../api/trades'
import { analyzeSymbol, autoTrade } from '../../api/signals'
import { usePortfolioStore } from '../../store'
import { getPortfolio } from '../../api/portfolio'
import LoadingSpinner from '../common/LoadingSpinner'

export default function TradePanel() {
  const [symbol, setSymbol] = useState('AAPL')
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [qty, setQty] = useState('')
  const [loading, setLoading] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [msg, setMsg] = useState('')
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio)

  const refresh = () => getPortfolio().then(setPortfolio).catch(console.error)

  const handleOrder = async () => {
    if (!qty || isNaN(Number(qty))) return
    setLoading(true)
    setMsg('')
    try {
      const trade = await placeOrder({ symbol: symbol.toUpperCase(), side, quantity: Number(qty) })
      setMsg(`${side} ${qty} ${symbol.toUpperCase()} filled @ $${trade.price.toFixed(2)}`)
      await refresh()
    } catch (e: any) {
      setMsg(`Error: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleAutoTrade = async () => {
    setAiLoading(true)
    setMsg('')
    try {
      const result = await autoTrade(symbol.toUpperCase(), 0.1)
      setMsg(`AI Signal: ${result.signal} (${(result.confidence * 100).toFixed(0)}% conf)${result.trade ? ` — Trade executed` : ''}`)
      await refresh()
    } catch (e: any) {
      setMsg(`Error: ${e.message}`)
    } finally {
      setAiLoading(false)
    }
  }

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
      <div className="text-sm font-medium text-gray-300 mb-3">Trade Panel</div>

      <div className="space-y-3">
        <input
          className="input-field w-full"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          placeholder="Symbol (e.g. AAPL)"
        />

        <div className="flex gap-2">
          <button
            onClick={() => setSide('BUY')}
            className={`flex-1 py-2 rounded text-sm font-medium transition-colors ${side === 'BUY' ? 'bg-accent-green text-white' : 'bg-surface-700 text-gray-400 hover:text-gray-200'}`}
          >
            BUY
          </button>
          <button
            onClick={() => setSide('SELL')}
            className={`flex-1 py-2 rounded text-sm font-medium transition-colors ${side === 'SELL' ? 'bg-accent-red text-white' : 'bg-surface-700 text-gray-400 hover:text-gray-200'}`}
          >
            SELL
          </button>
        </div>

        <input
          className="input-field w-full"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          placeholder="Quantity"
          type="number"
          min="0"
        />

        <button
          onClick={handleOrder}
          disabled={loading}
          className={`w-full py-2 rounded text-sm font-medium flex items-center justify-center gap-2 transition-colors ${side === 'BUY' ? 'btn-success' : 'btn-danger'}`}
        >
          {loading ? <LoadingSpinner size="sm" /> : null}
          {loading ? 'Executing...' : `Place ${side} Order`}
        </button>

        <div className="border-t border-surface-600 pt-3">
          <button
            onClick={handleAutoTrade}
            disabled={aiLoading}
            className="w-full btn-primary flex items-center justify-center gap-2"
          >
            {aiLoading ? <LoadingSpinner size="sm" /> : <span>⚡</span>}
            {aiLoading ? 'Analyzing...' : 'AI Auto-Trade'}
          </button>
        </div>

        {msg && (
          <div className="text-xs bg-surface-700 border border-surface-600 rounded px-3 py-2 text-gray-300">
            {msg}
          </div>
        )}
      </div>
    </div>
  )
}
