import React from 'react'

const ICONS = {
  phone_detected:    '📱',
  out_of_seat:       '🚶',
  distracted_gaze:   '👀',
  writing_idle:      '✏️',
  fatigue_drowsy:    '😴',
  bad_posture_close: '📐',
  bad_posture_slouch:'🪑',
  break_studying:    '📚',
  break_sedentary:   '🧍',
  good_focus:        '⭐',
}

const PRIORITY_COLORS = {
  '3': 'border-red-500 bg-red-950',
  '2': 'border-amber-500 bg-amber-950',
  '1': 'border-slate-500 bg-slate-800',
}

const PRIORITY_LABELS = { '3': '高', '2': '中', '1': '低' }

const EVENT_LABELS = {
  phone_detected:    '检测到手机',
  out_of_seat:       '离开座位',
  distracted_gaze:   '注意力分散',
  writing_idle:      '停止书写',
  fatigue_drowsy:    '疲劳瞌睡',
  bad_posture_close: '距离过近',
  bad_posture_slouch:'坐姿不良',
  break_studying:    '休息时学习',
  break_sedentary:   '休息时久坐',
  good_focus:        '优秀专注',
}

function fmtTime(ts) {
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function EventTimeline({ events }) {
  if (!events || events.length === 0) {
    return (
      <div className="bg-slate-800 rounded-2xl p-6 shadow-lg">
        <h2 className="text-lg font-semibold text-slate-200 mb-4">事件记录</h2>
        <p className="text-slate-500 text-sm text-center py-8">暂无事件</p>
      </div>
    )
  }

  const sorted = [...events].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))

  return (
    <div className="bg-slate-800 rounded-2xl p-6 shadow-lg">
      <h2 className="text-lg font-semibold text-slate-200 mb-4">
        事件记录 <span className="text-sm text-slate-400 font-normal">({events.length})</span>
      </h2>
      <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
        {sorted.map((ev, i) => {
          const pkey = String(ev.priority)
          return (
            <div key={i}
              className={`border-l-4 rounded-r-lg px-3 py-2 flex items-start gap-3 ${PRIORITY_COLORS[pkey] ?? PRIORITY_COLORS['1']}`}>
              <span className="text-xl leading-none mt-0.5">{ICONS[ev.event_type] ?? '⚡'}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-200">
                  {EVENT_LABELS[ev.event_type] ?? ev.event_type}
                  <span className="ml-2 text-xs text-slate-400">
                    [{PRIORITY_LABELS[pkey] ?? pkey}]
                  </span>
                </p>
                <p className="text-xs text-slate-400">{fmtTime(ev.timestamp)}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
