import React, { useState } from 'react'
import { createRequest, scoreRequest } from '../api'

const S = {
  page:  { padding: '32px', maxWidth: 1100, margin: '0 auto' },
  h1:    { fontFamily: 'Georgia,serif', fontSize: 36, color: 'white', marginBottom: 8 },
  sub:   { fontSize: 14, color: 'rgba(255,255,255,0.45)', marginBottom: 40 },
  card:  { background: '#1A0810', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: 28, marginBottom: 20 },
  label: { fontSize: 11, color: 'rgba(255,255,255,0.35)', letterSpacing: 2, textTransform: 'uppercase', marginBottom: 12 },
  input: {
    width: '100%', padding: '8px 12px', background: 'rgba(255,255,255,0.06)',
    border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6,
    color: 'white', fontSize: 13, marginBottom: 14,
  },
  btn:   { padding: '10px 24px', background: '#BE1228', color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13, fontWeight: 600 },
}

export default function Home({ token }) {
  const [message, setMessage] = useState('')
  const [parsed, setParsed]   = useState(null)
  const [loading, setLoading] = useState(false)

  const testPII = async () => {
    if (!token) { alert('Authenticate first'); return }
    if (!message.trim()) return
    setLoading(true)
    try {
      const res = await fetch(
        `http://localhost:8000/requests/parse?text=${encodeURIComponent(message)}`,
        { method: 'POST', headers: { Authorization: `Bearer ${token}` } }
      )
      const data = await res.json()
      setParsed(data)
    } catch (e) {
      alert('Parse failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={S.page}>
      <h1 style={S.h1}>🔍 NLP Pipeline Demo</h1>
      <p style={S.sub}>
        Natural language blood request parsing — Bengali, English, and Banglish.
        The PII scrubber strips identity information before relay.
      </p>

      <div style={S.card}>
        <div style={S.label}>Natural Language Request Parser</div>
        <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', marginBottom: 16 }}>
          Type a blood request in any language — English, Bengali, or mixed Banglish.
          The NLP pipeline extracts structured fields.
        </p>

        <textarea
          value={message}
          onChange={e => setMessage(e.target.value)}
          placeholder="e.g. আমার মায়ের জন্য O নেগেটিভ রক্ত দরকার ঢাকা মেডিকেলে আজকে&#10;or: need 2 bags O- urgent DMCH my number is 01711123456"
          style={{ ...S.input, height: 100, resize: 'vertical', fontFamily: 'inherit' }}
        />

        <button onClick={testPII} disabled={loading} style={S.btn}>
          {loading ? 'Parsing...' : 'Parse Request'}
        </button>

        {parsed && (
          <div style={{ marginTop: 20 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
              {[
                ['Blood Group', parsed.blood_group || '—'],
                ['Units', parsed.units_needed || 1],
                ['Urgency', parsed.urgency || '—'],
                ['Hospital', parsed.hospital_name || '—'],
                ['Parsed by', parsed.parsed_by],
                ['Notes', parsed.notes?.slice(0,40) + '...' || '—'],
              ].map(([k, v]) => (
                <div key={k} style={{
                  padding: 14, background: 'rgba(255,255,255,0.04)',
                  borderRadius: 8, border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 4 }}>{k}</div>
                  <div style={{ fontSize: 14, color: 'white', fontWeight: 600 }}>{String(v)}</div>
                </div>
              ))}
            </div>

            {parsed.parsed_by === 'claude' && (
              <div style={{ marginTop: 12, padding: 10,
                background: 'rgba(190,18,40,0.1)', borderRadius: 6,
                fontSize: 11, color: '#FF8090' }}>
                ✓ Claude API used for complex/Bengali parsing
              </div>
            )}
          </div>
        )}
      </div>

      {/* PII Scrubber demo */}
      <div style={S.card}>
        <div style={S.label}>Privacy Architecture</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {[
            ['🔒 No Name Sharing', 'Donor names, phone numbers, and photos are never transmitted to requesters.'],
            ['📍 Fuzzy Location', 'Only district or upazila level shared — never GPS coordinates.'],
            ['💬 Relay-Based Chat', 'All messages pass through the PII scrubber before relay.'],
            ['🗑️ Auto-Delete', 'Chat channels permanently deleted 24 hours after donation confirmation.'],
          ].map(([title, desc]) => (
            <div key={title} style={{ padding: 16, background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'white', marginBottom: 6 }}>{title}</div>
              <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', lineHeight: 1.6 }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}