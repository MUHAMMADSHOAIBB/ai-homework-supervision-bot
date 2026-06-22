import React, { useState, useEffect, useCallback, useRef } from 'react'
import StatusCard from './components/StatusCard.jsx'
import EventTimeline from './components/EventTimeline.jsx'
import { FocusLineChart, WeekBarChart } from './components/FocusChart.jsx'
import SessionSummary from './components/SessionSummary.jsx'
import {
  getCurrentSession, startSession, stopSession,
  getEvents, getSnapshots, getHistory,
  subscribeToFeatures, sendChat, coachGreet,
} from './api/client.js'

const DEFAULT_NAME = 'shoaib'

// ── Chat Panel ────────────────────────────────────────────────────────────────
function ChatPanel({ isActive, live, session }) {
  const [open, setOpen]       = useState(false)
  const [messages, setMessages] = useState([
    { role: 'coach', text: "Hi! I'm your Coach 👋 Ask me anything or just chat!" }
  ])
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)
  const [listening, setListening] = useState(false)
  const bottomRef  = useRef(null)
  const inputRef   = useRef(null)
  const recognRef  = useRef(null)

  // Auto-scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  const addMessage = (role, text) =>
    setMessages(prev => [...prev, { role, text, time: new Date().toLocaleTimeString() }])

  const send = async (text) => {
    const msg = text.trim()
    if (!msg || loading) return
    addMessage('student', msg)
    setInput('')
    setLoading(true)
    try {
      const data = await sendChat(msg)
      addMessage('coach', data.reply)
    } catch {
      addMessage('coach', "Sorry, I couldn't reach the server. Try again!")
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  // Voice input via browser Web Speech API
  const toggleVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { alert('Voice input is not supported in this browser. Use Chrome.'); return }

    if (listening) {
      recognRef.current?.stop()
      setListening(false)
      return
    }

    const recog = new SR()
    recog.lang = 'en-US'   // change to 'zh-CN' if using Chinese
    recog.interimResults = false
    recog.maxAlternatives = 1
    recognRef.current = recog

    recog.onresult = (e) => {
      const transcript = e.results[0][0].transcript
      setInput(transcript)
      setListening(false)
      // Auto-send voice message
      send(transcript)
    }
    recog.onerror = () => setListening(false)
    recog.onend   = () => setListening(false)

    recog.start()
    setListening(true)
  }

  const handleGreet = async () => {
    setLoading(true)
    try {
      const data = await coachGreet()
      addMessage('coach', data.greeting)
    } catch {
      addMessage('coach', "Let's get started! Focus time begins now. You got this!")
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* Floating chat button */}
      <button
        onClick={() => setOpen(o => !o)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-2xl flex items-center justify-center text-2xl transition-all"
        style={{ background: open ? '#ef4444' : '#3b82f6' }}
        title="Chat with Coach"
      >
        {open ? '✕' : '💬'}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 w-80 flex flex-col rounded-2xl shadow-2xl overflow-hidden"
             style={{ height: '480px', background: '#1e293b', border: '1px solid #334155' }}>

          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3" style={{ background: '#0f172a' }}>
            <div className="w-9 h-9 rounded-full flex items-center justify-center text-lg"
                 style={{ background: '#3b82f6' }}>🤖</div>
            <div>
              <p className="text-white font-semibold text-sm">Coach AI</p>
              <p className="text-xs" style={{ color: '#22c55e' }}>● Online — deepseek-v4-flash</p>
            </div>
            {isActive && (
              <button
                onClick={handleGreet}
                disabled={loading}
                className="ml-auto text-xs px-2 py-1 rounded-lg"
                style={{ background: '#1d4ed8', color: '#fff' }}
                title="Ask coach for an opening greeting"
              >
                👋 Greet
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'student' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className="max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed"
                  style={{
                    background: m.role === 'student' ? '#3b82f6' : '#334155',
                    color: '#f1f5f9',
                    borderRadius: m.role === 'student' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                  }}
                >
                  {m.role === 'coach' && (
                    <span className="text-xs font-semibold block mb-1" style={{ color: '#60a5fa' }}>
                      Coach
                    </span>
                  )}
                  {m.text}
                  {m.time && (
                    <span className="text-xs block mt-1 opacity-50">{m.time}</span>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="rounded-2xl px-4 py-2 text-sm"
                     style={{ background: '#334155', color: '#94a3b8' }}>
                  <span className="animate-pulse">Coach is thinking...</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Live context strip */}
          {live && (
            <div className="px-3 py-1 text-xs flex gap-2 flex-wrap"
                 style={{ background: '#0f172a', color: '#64748b' }}>
              <span>Work: {live.work_confidence ?? '–'}</span>
              <span>Phase: {live.pomodoro_state}</span>
              <span>{live.face_present ? '😊 Face' : '❌ No face'}</span>
              {live.phone_detected && <span style={{ color: '#f87171' }}>📱 Phone!</span>}
            </div>
          )}

          {/* Input row */}
          <div className="flex items-center gap-2 px-3 py-3"
               style={{ background: '#0f172a', borderTop: '1px solid #1e293b' }}>

            {/* Mic button */}
            <button
              onClick={toggleVoice}
              className="w-9 h-9 rounded-full flex items-center justify-center text-lg flex-shrink-0 transition-all"
              style={{ background: listening ? '#ef4444' : '#334155' }}
              title={listening ? 'Stop recording' : 'Speak to Coach'}
            >
              {listening ? '⏹' : '🎤'}
            </button>

            {/* Text input */}
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={listening ? '🎤 Listening...' : 'Ask or chat...'}
              disabled={loading || listening}
              className="flex-1 rounded-xl px-3 py-2 text-sm outline-none"
              style={{ background: '#1e293b', color: '#f1f5f9', border: '1px solid #334155' }}
            />

            {/* Send button */}
            <button
              onClick={() => send(input)}
              disabled={!input.trim() || loading}
              className="w-9 h-9 rounded-full flex items-center justify-center text-lg flex-shrink-0 transition-all disabled:opacity-40"
              style={{ background: '#3b82f6' }}
              title="Send"
            >
              ➤
            </button>
          </div>

          {/* Voice hint */}
          <p className="text-center text-xs pb-2" style={{ color: '#475569' }}>
            🎤 click mic → speak → auto-sends · ⌨ type + Enter
          </p>
        </div>
      )}
    </>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [session, setSession]     = useState(null)
  const [live, setLive]           = useState(null)
  const [events, setEvents]       = useState([])
  const [snapshots, setSnapshots] = useState([])
  const [history, setHistory]     = useState([])
  const [summary, setSummary]     = useState(null)
  const [apiOk, setApiOk]         = useState(false)
  const [childName, setChildName] = useState(DEFAULT_NAME)
  const [loading, setLoading]     = useState(false)
  const [lang, setLang]           = useState('en')
  const pollRef = useRef(null)
  const sseRef  = useRef(null)

  const fetchSession = useCallback(async () => {
    try {
      const s = await getCurrentSession()
      setSession(s)
      setApiOk(true)
      if (s?.session_id) {
        const [evs, snaps] = await Promise.all([
          getEvents(s.session_id),
          getSnapshots(s.session_id),
        ])
        setEvents(evs)
        setSnapshots(snaps)
      }
    } catch {
      setApiOk(false)
    }
  }, [])

  useEffect(() => {
    fetchSession()
    pollRef.current = setInterval(fetchSession, 5000)
    return () => clearInterval(pollRef.current)
  }, [fetchSession])

  useEffect(() => {
    if (!apiOk) return
    sseRef.current = subscribeToFeatures((data) => setLive(data))
    return () => sseRef.current?.()
  }, [apiOk])

  useEffect(() => {
    if (!apiOk) return
    getHistory(1).then(setHistory).catch(() => {})
  }, [apiOk])

  const handleStart = async () => {
    setLoading(true)
    setSummary(null)
    try {
      await startSession(childName)
      await fetchSession()
    } catch {
      alert('Cannot connect to backend. Start the Python server first.')
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setLoading(true)
    try {
      const s = await stopSession()
      setSummary(s)
      setSession(null)
      setEvents([])
      setSnapshots([])
      await getHistory(1).then(setHistory).catch(() => {})
    } catch (e) {
      alert('Stop failed: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const toggleLang = async () => {
    const next = lang === 'en' ? 'zh' : 'en'
    setLang(next)
    try {
      await fetch('http://127.0.0.1:8000/session/language', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lang: next }),
      })
    } catch {}
  }

  const isActive = session?.pomodoro_state &&
    session.pomodoro_state !== 'IDLE' &&
    session.pomodoro_state !== 'COMPLETE'

  return (
    <div className="min-h-screen bg-slate-900 p-4 md:p-8">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">📚 AI Homework Supervisor</h1>
          <p className="text-sm text-slate-400 mt-1">
            {apiOk
              ? <>
                  <span className="text-green-400">● Backend connected (localhost:8000)</span>
                  <br/>
                  <span className="text-green-400">● 摄像头正常 Camera OK</span>
                </>
              : <span className="text-red-400">● Backend not connected — start the Python server</span>
            }
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Language toggle */}
          <button
            onClick={toggleLang}
            className="px-3 py-2 rounded-xl text-sm font-medium text-white"
            style={{ background: '#334155' }}
          >
            {lang === 'en' ? '中文' : 'English'}
          </button>

          {!isActive && (
            <input
              className="bg-slate-700 text-white rounded-lg px-3 py-2 text-sm w-28 outline-none border border-slate-600 focus:border-blue-500"
              value={childName}
              onChange={e => setChildName(e.target.value)}
              placeholder="Child name"
            />
          )}

          <button
            onClick={isActive ? handleStop : handleStart}
            disabled={loading}
            className={`px-6 py-2 rounded-xl font-semibold text-white transition-all ${
              isActive ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {loading ? '...' : isActive ? 'Stop Learning' : 'Start Learning'}
          </button>
        </div>
      </div>

      {/* Session summary */}
      {summary && (
        <div className="mb-6">
          <SessionSummary summary={summary} />
        </div>
      )}

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <StatusCard session={session} live={live} />
        <EventTimeline events={events} />
        <FocusLineChart snapshots={snapshots} />
        <WeekBarChart history={history} />
      </div>

      {/* Live debug bar */}
      {live && (
        <div className="mt-4 bg-slate-800 rounded-xl px-4 py-2 text-xs text-slate-400 flex flex-wrap gap-4">
          <span>Face: {live.face_present ? '✅' : '❌'}</span>
          <span>Phone: {live.phone_detected ? '🚨 Yes' : '✅ No'}</span>
          <span>Write: {live.writing_score}</span>
          <span>EAR: {live.ear_avg}</span>
          <span>State: {live.pomodoro_state}</span>
          <span>Used: {live.elapsed_seconds}s / {live.round_number}</span>
        </div>
      )}

      {/* Floating Chat Panel */}
      <ChatPanel isActive={isActive} live={live} session={session} />
    </div>
  )
}
