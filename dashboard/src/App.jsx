import React, { useState, useEffect } from 'react'
import { getHealth, register, verifyOtp } from './api'
import Home from './pages/Home'
import Hospital from './pages/Hospital'
import Agent from './pages/Agent'

const NAV_STYLE = {
  position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
  background: 'rgba(14,3,8,0.97)', backdropFilter: 'blur(16px)',
  borderBottom: '1px solid rgba(255,255,255,0.06)',
  height: 52, display: 'flex', alignItems: 'center',
  justifyContent: 'space-between', padding: '0 32px',
}

const PAGES = ['agent', 'hospital', 'home']

export default function App() {
  const [page, setPage]     = useState('agent')
  const [token, setToken]   = useState(null)
  const [health, setHealth] = useState(null)
  const [logging, setLogging] = useState(false)
  const [phone, setPhone]   = useState('01711123456')
  const [otp, setOtp]       = useState('')
  const [otpSent, setOtpSent] = useState(false)
  const [status, setStatus] = useState('')

  useEffect(() => {
    getHealth()
      .then(r => setHealth(r.data))
      .catch(() => setHealth({ status: 'unreachable' }))
  }, [])

  const handleRegister = async () => {
    try {
      setStatus('Sending OTP...')
      await register(phone, 'O-')
      setOtpSent(true)
      setStatus('OTP sent — check API logs for the code (dev mode)')
    } catch (e) {
      setStatus('Register failed: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleVerify = async () => {
    try {
      setStatus('Verifying...')
      const r = await verifyOtp(phone, otp)
      setToken(r.data.access_token)
      setStatus('✓ Authenticated')
    } catch (e) {
      setStatus('OTP invalid: ' + (e.response?.data?.detail || e.message))
    }
  }

  return (
    <div>
      {/* NAV */}
      <nav style={NAV_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 22, height: 22, background: '#BE1228',
            borderRadius: '50% 50% 50% 0', transform: 'rotate(-45deg)',
            position: 'relative',
          }}>
            <div style={{
              position: 'absolute', top: '50%', left: '50%',
              transform: 'translate(-50%,-50%) rotate(45deg)',
              width: 8, height: 8, background: 'white', borderRadius: '50%',
            }} />
          </div>
          <span style={{ fontFamily: 'Georgia,serif', fontSize: 16, color: 'white' }}>
            Rokto Setu
          </span>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', marginLeft: 4 }}>
            রক্ত সেতু · AI Engineer Portfolio Demo
          </span>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {PAGES.map(p => (
            <button key={p} onClick={() => setPage(p)} style={{
              padding: '5px 14px',
              background: page === p ? '#BE1228' : 'rgba(255,255,255,0.06)',
              color: page === p ? 'white' : 'rgba(255,255,255,0.5)',
              border: 'none', borderRadius: 4, cursor: 'pointer',
              fontSize: 11, textTransform: 'uppercase', letterSpacing: 1,
            }}>
              {p === 'agent' ? 'Agent Logs' : p === 'hospital' ? 'Hospital' : 'Request Demo'}
            </button>
          ))}

          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: health?.status === 'healthy' ? '#4ADE80' : '#f87171',
            marginLeft: 8,
          }} />
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>
            {health?.database || 'connecting...'}
          </span>
        </div>
      </nav>

      {/* AUTH BANNER */}
      {!token && (
        <div style={{
          marginTop: 52, padding: '12px 32px',
          background: 'rgba(190,18,40,0.15)',
          borderBottom: '1px solid rgba(190,18,40,0.3)',
          display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        }}>
          <span style={{ fontSize: 12, color: '#FF8090' }}>
            Auth required to use demo endpoints:
          </span>
          {!otpSent ? (
            <>
              <input value={phone} onChange={e => setPhone(e.target.value)}
                placeholder="Phone" style={INPUT_S} />
              <button onClick={handleRegister} style={BTN_S}>Send OTP</button>
            </>
          ) : (
            <>
              <input value={otp} onChange={e => setOtp(e.target.value)}
                placeholder="Enter OTP from API logs" style={INPUT_S} />
              <button onClick={handleVerify} style={BTN_S}>Verify</button>
            </>
          )}
          <span style={{ fontSize: 11, color: '#FF8090' }}>{status}</span>
        </div>
      )}

      {/* PAGES */}
      <div style={{ marginTop: token ? 52 : 100 }}>
        {page === 'agent'    && <Agent    token={token} />}
        {page === 'hospital' && <Hospital token={token} />}
        {page === 'home'     && <Home     token={token} />}
      </div>
    </div>
  )
}

const INPUT_S = {
  padding: '5px 10px', background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.15)', borderRadius: 4,
  color: 'white', fontSize: 12, width: 160,
}
const BTN_S = {
  padding: '5px 14px', background: '#BE1228', color: 'white',
  border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12,
}