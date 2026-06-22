const BASE = 'http://127.0.0.1:8000'

export async function getCurrentSession() {
  const r = await fetch(`${BASE}/session/current`)
  if (!r.ok) throw new Error('API unavailable')
  return r.json()
}

export async function startSession(childName, childAge = 10) {
  const r = await fetch(`${BASE}/session/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ child_name: childName, child_age: childAge }),
  })
  if (!r.ok) throw new Error('Failed to start session')
  return r.json()
}

export async function stopSession() {
  const r = await fetch(`${BASE}/session/stop`, { method: 'POST' })
  if (!r.ok) throw new Error('Failed to stop session')
  return r.json()
}

export async function getEvents(sessionId) {
  const r = await fetch(`${BASE}/session/${sessionId}/events`)
  if (!r.ok) return []
  return r.json()
}

export async function getSnapshots(sessionId) {
  const r = await fetch(`${BASE}/session/${sessionId}/snapshots`)
  if (!r.ok) return []
  return r.json()
}

export async function getHistory(childId, days = 7) {
  const r = await fetch(`${BASE}/history/${childId}?days=${days}`)
  if (!r.ok) return []
  return r.json()
}

export async function getChildren() {
  const r = await fetch(`${BASE}/children`)
  if (!r.ok) return []
  return r.json()
}

export function subscribeToFeatures(onData) {
  const es = new EventSource(`${BASE}/stream/features`)
  es.onmessage = (e) => {
    try { onData(JSON.parse(e.data)) } catch {}
  }
  es.onerror = () => {}
  return () => es.close()
}

export async function sendChat(message) {
  const r = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!r.ok) throw new Error('Chat failed')
  return r.json()
}

export async function coachGreet() {
  const r = await fetch(`${BASE}/coach/greet`, { method: 'POST' })
  if (!r.ok) throw new Error('Greet failed')
  return r.json()
}
