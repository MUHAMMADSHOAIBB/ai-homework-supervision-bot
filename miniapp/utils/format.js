function fmtTimer(sec) {
  sec = Math.max(0, Math.round(sec))
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function fmtMinSec(sec) {
  sec = Math.max(0, Math.round(sec))
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (h > 0) return `${h}时${m}分`
  return `${m}分`
}

function fmtTime(ts) {
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

function fmtDate(ts) {
  const d = new Date(ts)
  const days = ['日','一','二','三','四','五','六']
  return days[d.getDay()]
}

module.exports = { fmtTimer, fmtMinSec, fmtTime, fmtDate }
