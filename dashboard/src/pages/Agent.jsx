import React, { useState } from 'react'
import { createRequest, scoreRequest } from '../api'

const S = {
  page:    { padding: '32px', maxWidth: 1100, margin: '0 auto' },
  heading: { fontFamily: 'Georgia,serif', fontSize: 36, color: 'white', marginBottom: 8 },
  sub:     { fontSize: 14, color: 'rgba(255,255,255,0.45)', marginBottom: 40 },
  grid:    { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 },
  card:    {
    background: '#1A0810', border: '1px solid rgba(255,255,255,0.07)',
    borderRadius: 14, padding: 28,
  },
  label:   { fontSize: 11, color: 'rgba(255,255,255,0.35)', letterSpacing: 2,
             textTransform: 'uppercase', marginBottom: 8 },
  select:  {
    width: '100%', padding: '8px 12px', background: 'rgba(255,255,255,0.06)',
    border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6,
    color: 'white', fontSize: 13, marginBottom: 14,
  },
  btn:     {
    width: '100%', padding: '10px 0', background: '#BE1228',
    color: 'white', border: 'none', borderRadius: 6,
    cursor: 'pointer', fontSize: 13, fontWeight: 600,
  },
  log:     {
    background: '#0A0205', borderRadius: 8, padding: 16,
    fontFamily: 'monospace', fontSize: 11, color: '#7DF0A8',
    minHeight: 300, maxHeight: 420, overflowY: 'auto',
    whiteSpace: 'pre-wrap', lineHeight: 1.8,
  },
  step:    { marginBottom: 8, padding: '8px 12px',
             background: 'rgba(255,255,255,0.04)', borderRadius: 6 },
}

const BLOOD_GROUPS = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
const URGENCIES    = ['EMERGENCY', 'URGENT', 'PLANNED']

export default function Agent({ token }) {
  const [bloodGroup, setBloodGroup] = useState('O-')
  const [urgency, setUrgency]       = useState('EMERGENCY')
  const [units, setUnits]           = useState(2)
  const [agentLog, setAgentLog]     = useState('')
  const [running, setRunning]       = useState(false)
  const [matched, setMatched]       = useState(null)

  // Anomaly demo state
  const [reqPerHour, setReqPerHour] = useState(0)
  const [reqPerDay,  setReqPerDay]  = useState(1)
  const [anomResult, setAnomResult] = useState(null)
  const [anomLoading, setAnomLoading] = useState(false)

  const runAgent = async () => {
    if (!token) { alert('Authenticate first using the banner above'); return }
    setRunning(true)
    setMatched(null)
    setAgentLog('Starting matching agent...\n')

    try {
      const res = await createRequest(token, {
        blood_group: bloodGroup, units_needed: units,
        urgency, hospital_name: 'Dhaka Medical College Hospital',
        message: 'Demo request — portfolio showcase',
        division_id: 1, district_id: 1, upazila_id: 101, union_id: 1001,
      })

      setAgentLog(prev => prev +
        `\n✓ Request created: ${res.data.request_id?.slice(0,8)}...\n` +
        `Blood group: ${bloodGroup} | Urgency: ${urgency}\n\n` +
        `Agent is running in background — check API container logs:\n` +
        `  docker logs rokto_api --tail 40\n\n` +
        `Expected flow:\n` +
        `  1. Search at UPAZILA tier\n` +
        `  2. If < 3 donors → expand to DISTRICT\n` +
        `  3. If < 3 donors → expand to DIVISION\n` +
        `  4. Rank by proximity + history + badge\n` +
        `  5. Notify top 3 donors\n` +
        `  6. Match confirmed\n\n` +
        `Agent status: ${res.data.agent_status}`
      )
      setMatched(res.data)
    } catch (e) {
      setAgentLog(prev => prev + `\nError: ${e.response?.data?.detail || e.message}`)
    } finally {
      setRunning(false)
    }
  }

  const checkAnomaly = async () => {
    if (!token) { alert('Authenticate first'); return }
    setAnomLoading(true)
    setAnomResult(null)
    try {
      const res = await scoreRequest(token, {
        units_needed: parseInt(units), urgency, blood_group: bloodGroup,
        district_id: 1, division_id: 1, hour_of_day: new Date().getHours(),
        is_weekend: [0,6].includes(new Date().getDay()),
        requests_last_hour: parseInt(reqPerHour),
        requests_last_day:  parseInt(reqPerDay),
        same_location_reqs: parseInt(reqPerHour) > 2 ? 3 : 0,
      })
      setAnomResult(res.data)
    } catch (e) {
      alert('Anomaly check failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setAnomLoading(false)
    }
  }

  return (
    <div style={S.page}>
      <h1 style={S.heading}>🤖 LangGraph Matching Agent</h1>
      <p style={S.sub}>
        Autonomous donor matching — searches by geographic tier, ranks donors,
        expands radius if needed, notifies top matches. Every decision logged.
      </p>

      <div style={S.grid}>
        {/* LEFT: Request form */}
        <div style={S.card}>
          <div style={S.label}>Blood Request Parameters</div>

          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', marginBottom: 8 }}>Blood Group</div>
          <select value={bloodGroup} onChange={e => setBloodGroup(e.target.value)} style={S.select}>
            {BLOOD_GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
          </select>

          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', marginBottom: 8 }}>Urgency</div>
          <select value={urgency} onChange={e => setUrgency(e.target.value)} style={S.select}>
            {URGENCIES.map(u => <option key={u} value={u}>{u}</option>)}
          </select>

          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', marginBottom: 8 }}>
            Units needed: {units}
          </div>
          <input type="range" min={1} max={5} value={units}
            onChange={e => setUnits(e.target.value)}
            style={{ width: '100%', marginBottom: 20 }} />

          <button onClick={runAgent} disabled={running} style={{
            ...S.btn,
            background: running ? 'rgba(190,18,40,0.4)' : '#BE1228',
          }}>
            {running ? 'Agent Running...' : '▶  Run Matching Agent'}
          </button>

          {matched && (
            <div style={{
              marginTop: 16, padding: 14,
              background: 'rgba(74,222,128,0.08)',
              border: '1px solid rgba(74,222,128,0.2)',
              borderRadius: 8,
            }}>
              <div style={{ fontSize: 11, color: '#4ADE80', marginBottom: 4 }}>
                ✓ REQUEST SUBMITTED
              </div>
              <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)' }}>
                ID: {matched.request_id?.slice(0,16)}...<br/>
                Status: {matched.status}<br/>
                {matched.agent_status}
              </div>
            </div>
          )}
        </div>

        {/* RIGHT: Agent log */}
        <div style={S.card}>
          <div style={S.label}>Agent Decision Log</div>
          <div style={S.log}>
            {agentLog || 'Agent log will appear here after submitting a request.\n\nThe agent:\n  1. Searches donors at UPAZILA tier\n  2. Ranks by proximity + history\n  3. Expands if insufficient donors\n  4. Notifies top 3\n  5. Confirms match\n\nFull logs: docker logs rokto_api --tail 50'}
          </div>
          <div style={{
            marginTop: 8, fontSize: 10,
            color: 'rgba(255,255,255,0.2)', letterSpacing: 1,
          }}>
            REAL-TIME AGENT DECISIONS · LANGGRAPH · CLAUDE API
          </div>
        </div>
      </div>

      {/* Anomaly Detection Demo */}
      <div style={{ marginTop: 24, ...S.card }}>
        <div style={S.label}>🔍 Isolation Forest — Anomaly Detection</div>
        <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', marginBottom: 20 }}>
          Simulate a suspicious request pattern to see the anomaly detector in action.
          Increase the request frequency to trigger a QUARANTINE verdict.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 16, alignItems: 'end' }}>
          <div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginBottom: 6 }}>
              Requests last hour: {reqPerHour}
            </div>
            <input type="range" min={0} max={10} value={reqPerHour}
              onChange={e => setReqPerHour(e.target.value)} style={{ width: '100%' }} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginBottom: 6 }}>
              Requests today: {reqPerDay}
            </div>
            <input type="range" min={0} max={20} value={reqPerDay}
              onChange={e => setReqPerDay(e.target.value)} style={{ width: '100%' }} />
          </div>
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)' }}>
            Tip: set both sliders high to trigger QUARANTINE
          </div>
          <button onClick={checkAnomaly} disabled={anomLoading} style={{
            ...S.btn, width: 'auto', padding: '10px 20px',
          }}>
            {anomLoading ? 'Scoring...' : 'Check Anomaly'}
          </button>
        </div>

        {anomResult && (
          <div style={{
            marginTop: 20, padding: 20, borderRadius: 10,
            background: anomResult.verdict === 'QUARANTINE'
              ? 'rgba(248,113,113,0.08)' : 'rgba(74,222,128,0.08)',
            border: `1px solid ${anomResult.verdict === 'QUARANTINE'
              ? 'rgba(248,113,113,0.3)' : 'rgba(74,222,128,0.3)'}`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{
                fontSize: 18, fontWeight: 700,
                color: anomResult.verdict === 'QUARANTINE' ? '#f87171' : '#4ADE80',
              }}>
                {anomResult.verdict === 'QUARANTINE' ? '🚨 QUARANTINE' : '✓ NORMAL'}
              </span>
              <span style={{ fontSize: 14, color: 'rgba(255,255,255,0.6)' }}>
                Anomaly score: <strong style={{ color: 'white' }}>
                  {(anomResult.anomaly_score * 100).toFixed(1)}%
                </strong>
                {' '}(threshold: {(anomResult.threshold * 100).toFixed(0)}%)
              </span>
            </div>
            {anomResult.risk_factors?.length > 0 && (
              <div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginBottom: 8 }}>
                  RISK FACTORS DETECTED:
                </div>
                {anomResult.risk_factors.map((r, i) => (
                  <div key={i} style={{
                    fontSize: 12, color: '#FCA5A5', padding: '4px 0',
                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                  }}>
                    • {r}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}