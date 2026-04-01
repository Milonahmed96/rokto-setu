import React, { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { getForecast, getModelInfo, getAnomalyInfo } from '../api'

const S = {
  page:  { padding: '32px', maxWidth: 1100, margin: '0 auto' },
  h1:    { fontFamily: 'Georgia,serif', fontSize: 36, color: 'white', marginBottom: 8 },
  sub:   { fontSize: 14, color: 'rgba(255,255,255,0.45)', marginBottom: 40 },
  grid:  { display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: 24 },
  card:  { background: '#1A0810', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: 28 },
  label: { fontSize: 11, color: 'rgba(255,255,255,0.35)', letterSpacing: 2, textTransform: 'uppercase', marginBottom: 14 },
  btn:   { padding: '8px 20px', background: '#BE1228', color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12 },
}

const RISK_COLORS = { HIGH: '#f87171', MEDIUM: '#fbbf24', LOW: '#4ADE80' }
const DISTRICTS = [
  { id: 1, name: 'Dhaka', div: 1 }, { id: 7, name: 'Chittagong', div: 2 },
  { id: 9, name: 'Sylhet', div: 3 }, { id: 11, name: 'Rajshahi', div: 4 },
  { id: 12, name: 'Khulna', div: 5 },
]

export default function Hospital({ token }) {
  const [district, setDistrict]   = useState(DISTRICTS[0])
  const [forecast, setForecast]   = useState(null)
  const [modelInfo, setModelInfo] = useState(null)
  const [anomInfo, setAnomInfo]   = useState(null)
  const [loading, setLoading]     = useState(false)

  const load = async () => {
    if (!token) return
    setLoading(true)
    try {
      const [f, m, a] = await Promise.all([
        getForecast(token, district.id, district.div),
        getModelInfo(token),
        getAnomalyInfo(token),
      ])
      setForecast(f.data)
      setModelInfo(m.data)
      setAnomInfo(a.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (token) load() }, [token, district])

  const chartData = forecast?.predictions?.map(p => ({
    name: p.blood_group,
    value: Math.round(p.shortage_prob * 100),
    risk: p.risk,
  })) || []

  return (
    <div style={S.page}>
      <h1 style={S.h1}>🏥 Hospital Partner Dashboard</h1>
      <p style={S.sub}>
        7-day blood shortage forecast with 90% conformal prediction intervals.
        LightGBM model + SHAP interpretability.
      </p>

      {!token && (
        <div style={{ padding: 24, background: 'rgba(190,18,40,0.1)', borderRadius: 10, marginBottom: 24 }}>
          <p style={{ color: '#FF8090', fontSize: 14 }}>
            Authenticate using the banner above to load forecast data.
          </p>
        </div>
      )}

      {/* District selector */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap' }}>
        {DISTRICTS.map(d => (
          <button key={d.id} onClick={() => setDistrict(d)} style={{
            padding: '6px 16px',
            background: district.id === d.id ? '#BE1228' : 'rgba(255,255,255,0.06)',
            color: district.id === d.id ? 'white' : 'rgba(255,255,255,0.5)',
            border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12,
          }}>
            {d.name}
          </button>
        ))}
        {loading && <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', alignSelf: 'center' }}>
          Loading...
        </span>}
      </div>

      <div style={S.grid}>
        {/* Forecast chart */}
        <div style={S.card}>
          <div style={S.label}>
            Blood Shortage Probability — {district.name} — Next 7 Days
          </div>

          {forecast && (
            <>
              <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
                {['HIGH', 'MEDIUM', 'LOW'].map(r => (
                  <div key={r} style={{
                    padding: '4px 12px', borderRadius: 4, fontSize: 11,
                    background: `${RISK_COLORS[r]}22`,
                    color: RISK_COLORS[r],
                    border: `1px solid ${RISK_COLORS[r]}44`,
                  }}>
                    {r}: {forecast.predictions?.filter(p => p.risk === r).length} groups
                  </div>
                ))}
                <div style={{ marginLeft: 'auto', fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>
                  Alert: {forecast.summary?.alert_level}
                </div>
              </div>

              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }} />
                  <YAxis tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }}
                    tickFormatter={v => `${v}%`} domain={[0, 100]} />
                  <Tooltip
                    formatter={v => [`${v}%`, 'Shortage prob.']}
                    contentStyle={{ background: '#1A0810', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                    labelStyle={{ color: 'white' }}
                  />
                  <Bar dataKey="value" radius={[4,4,0,0]}>
                    {chartData.map((d, i) => (
                      <Cell key={i} fill={RISK_COLORS[d.risk] || '#4ADE80'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>

              <div style={{ marginTop: 12, fontSize: 11, color: 'rgba(255,255,255,0.25)' }}>
                90% Conformal Prediction Intervals · Forecast date: {forecast.forecast_date}
              </div>
            </>
          )}
        </div>

        {/* Model info */}
        <div>
          {modelInfo && (
            <div style={{ ...S.card, marginBottom: 16 }}>
              <div style={S.label}>Forecasting Model</div>
              <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)', lineHeight: 2 }}>
                <div>Type: <span style={{ color: 'white' }}>{modelInfo.model_type}</span></div>
                <div>RMSE: <span style={{ color: 'white' }}>{modelInfo.rmse?.toFixed(4)}</span></div>
                <div>Coverage: <span style={{ color: '#4ADE80' }}>{modelInfo.coverage_target}</span></div>
                <div>q̂: <span style={{ color: 'white' }}>{modelInfo.q_hat?.toFixed(4)}</span></div>
              </div>
              <div style={{ marginTop: 14 }}>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', marginBottom: 8 }}>
                  TOP FEATURES (SHAP)
                </div>
                {modelInfo.top_features?.slice(0,5).map(([feat, val]) => (
                  <div key={feat} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', width: 120, flexShrink: 0 }}>
                      {feat}
                    </div>
                    <div style={{
                      height: 6, borderRadius: 3, background: '#BE1228',
                      width: `${Math.min(val * 500, 100)}%`,
                    }} />
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>
                      {val?.toFixed(3)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {anomInfo && (
            <div style={S.card}>
              <div style={S.label}>Anomaly Detector</div>
              <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)', lineHeight: 2 }}>
                <div>Type: <span style={{ color: 'white' }}>Isolation Forest</span></div>
                <div>Precision: <span style={{ color: '#4ADE80' }}>{(anomInfo.normal_precision * 100).toFixed(1)}%</span></div>
                <div>Threshold: <span style={{ color: 'white' }}>{anomInfo.threshold}</span></div>
                <div>Trained: <span style={{ color: 'white' }}>
                  {anomInfo.trained_at?.slice(0,10)}
                </span></div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}