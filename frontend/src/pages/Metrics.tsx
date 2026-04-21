import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import './Metrics.css'

interface ModelMetrics {
  name: string
  provider: string
  context_length: number
  cost_per_1k: number
}

const MOCK_LATENCY = [
  { time: '00:00', llama3: 320, mistral: 280 },
  { time: '04:00', llama3: 350, mistral: 295 },
  { time: '08:00', llama3: 400, mistral: 330 },
  { time: '12:00', llama3: 380, mistral: 310 },
  { time: '16:00', llama3: 360, mistral: 290 },
  { time: '20:00', llama3: 330, mistral: 275 },
  { time: '24:00', llama3: 310, mistral: 265 },
]

const MOCK_QUERIES = [
  { time: 'Mon', queries: 42 }, { time: 'Tue', queries: 68 },
  { time: 'Wed', queries: 55 }, { time: 'Thu', queries: 79 },
  { time: 'Fri', queries: 91 }, { time: 'Sat', queries: 34 },
  { time: 'Sun', queries: 28 },
]

export default function Metrics() {
  const [models, setModels] = useState<ModelMetrics[]>([])
  const [latencyData] = useState(MOCK_LATENCY)
  const [queryData] = useState(MOCK_QUERIES)

  useEffect(() => {
    fetch('/api/models')
      .then(r => r.json())
      .then(d => setModels(d.models ?? []))
      .catch(() => {})
  }, [])

  return (
    <div className="metrics">
      <div className="page-header">
        <h1>Metrics</h1>
        <p>System performance, model stats, and optimizer diagnostics.</p>
      </div>

      {/* Latency chart */}
      <div className="card">
        <div className="card-header"><h2>Latency Over Time</h2></div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={latencyData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="time" tick={{ fontSize: 11, fill: '#8888aa' }} />
            <YAxis tick={{ fontSize: 11, fill: '#8888aa' }} unit="ms" />
            <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }} />
            <Legend />
            <Line type="monotone" dataKey="llama3" stroke="#b39ddb" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="mistral" stroke="#4fc3f7" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Queries per day */}
      <div className="card">
        <div className="card-header"><h2>Queries / Day</h2></div>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={queryData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="time" tick={{ fontSize: 11, fill: '#8888aa' }} />
            <YAxis tick={{ fontSize: 11, fill: '#8888aa' }} />
            <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }} />
            <Line type="monotone" dataKey="queries" stroke="#4caf50" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Model table */}
      <div className="card">
        <div className="card-header"><h2>Model Registry</h2></div>
        {models.length === 0 ? (
          <p className="text-muted text-sm">No models registered. Start Cortex with Ollama running.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Model</th><th>Provider</th><th>Context</th><th>Cost/1k tokens</th></tr>
              </thead>
              <tbody>
                {models.map(m => (
                  <tr key={m.name}>
                    <td className="text-accent">{m.name}</td>
                    <td className="text-muted text-sm">{m.provider}</td>
                    <td>{m.context_length?.toLocaleString() ?? '—'}</td>
                    <td>${m.cost_per_1k?.toFixed(3) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}