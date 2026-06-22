import React from 'react'

const STATE_COLORS = {
  IDLE:         'bg-gray-600',
  PREPARE:      'bg-green-700',
  FOCUS:        'bg-blue-700',
  BREAK:        'bg-teal-600',
  RESUME_CHECK: 'bg-yellow-600',
  COMPLETE:     'bg-purple-700',
}

const STATE_LABELS = {
  IDLE: '待机', PREPARE: '准备中', FOCUS: '专注中',
  BREAK: '休息中', RESUME_CHECK: '继续确认', COMPLETE: '完成',
}

function FocusIndicator({ live }) {
  if (!live) return <span className="inline-block w-3 h-3 rounded-full bg-gray-500 mr-2" />
  const { face_present, is_distracted, phone_detected } = live
  let color = 'bg-green-400'
  if (phone_detected) color = 'bg-red-500'
  else if (is_distracted || !face_present) color = 'bg-orange-400'
  return <span className={`inline-block w-3 h-3 rounded-full ${color} mr-2 animate-pulse`} />
}

function fmt(sec) {
  const m = Math.floor(sec / 60).toString().padStart(2, '0')
  const s = (sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export default function StatusCard({ session, live }) {
  const state = session?.pomodoro_state ?? 'IDLE'
  const badgeColor = STATE_COLORS[state] ?? 'bg-gray-600'

  return (
    <div className="bg-slate-800 rounded-2xl p-6 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-200">
          {session?.child_name ?? '—'} 的学习状态
        </h2>
        <span className={`px-3 py-1 rounded-full text-sm font-medium text-white ${badgeColor}`}>
          {STATE_LABELS[state] ?? state}
        </span>
      </div>

      <div className="flex items-center mb-3">
        <FocusIndicator live={live} />
        <span className="text-slate-300 text-sm">
          {live?.phone_detected ? '检测到手机！' :
           live?.is_distracted  ? '注意力分散' :
           live?.face_present   ? '专心学习中' : '未检测到人'}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-4 mt-4">
        <div className="text-center">
          <p className="text-2xl font-bold text-white">{fmt(session?.elapsed_seconds ?? 0)}</p>
          <p className="text-xs text-slate-400 mt-1">当前阶段</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-white">
            {live?.round_number ?? session?.round_number ?? 1}
          </p>
          <p className="text-xs text-slate-400 mt-1">第几轮</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-white">
            {Math.round(session?.focus_score_current ?? 0)}
          </p>
          <p className="text-xs text-slate-400 mt-1">专注分数</p>
        </div>
      </div>

      {session?.last_event && (
        <p className="mt-4 text-xs text-amber-400">
          最近事件: {session.last_event}
        </p>
      )}
    </div>
  )
}
