import React from 'react'

const EVENT_LABELS = {
  phone_detected: '手机使用',
  out_of_seat: '离座',
  distracted_gaze: '注意力分散',
  writing_idle: '停止书写',
  fatigue_drowsy: '疲劳',
  bad_posture_close: '距离过近',
  bad_posture_slouch: '坐姿不良',
  good_focus: '优秀专注',
}

function fmt(sec) {
  const m = Math.floor((sec ?? 0) / 60)
  const s = (sec ?? 0) % 60
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
}

export default function SessionSummary({ summary }) {
  if (!summary) return null

  const score = summary.focus_score_avg ?? 0
  const scoreColor = score >= 80 ? 'text-green-400' : score >= 50 ? 'text-amber-400' : 'text-red-400'

  return (
    <div className="bg-slate-800 rounded-2xl p-6 shadow-lg border border-purple-700">
      <h2 className="text-lg font-semibold text-purple-300 mb-4">🎉 本次学习总结</h2>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="text-center bg-slate-700 rounded-xl p-3">
          <p className="text-2xl font-bold text-white">{summary.rounds_completed ?? 0}</p>
          <p className="text-xs text-slate-400 mt-1">番茄钟</p>
        </div>
        <div className="text-center bg-slate-700 rounded-xl p-3">
          <p className="text-2xl font-bold text-white">{fmt(summary.total_focus_seconds)}</p>
          <p className="text-xs text-slate-400 mt-1">专注时长</p>
        </div>
        <div className="text-center bg-slate-700 rounded-xl p-3">
          <p className={`text-2xl font-bold ${scoreColor}`}>{Math.round(score)}</p>
          <p className="text-xs text-slate-400 mt-1">专注分数</p>
        </div>
      </div>

      {summary.event_counts && Object.keys(summary.event_counts).length > 0 && (
        <div className="mb-4">
          <p className="text-sm text-slate-400 mb-2">事件统计:</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(summary.event_counts).map(([k, v]) => (
              <span key={k} className="px-2 py-1 bg-slate-700 rounded-lg text-xs text-slate-300">
                {EVENT_LABELS[k] ?? k}: {v}
              </span>
            ))}
          </div>
        </div>
      )}

      {summary.ai_summary && (
        <p className="text-sm text-slate-300 bg-slate-700 rounded-xl p-3 italic">
          {summary.ai_summary}
        </p>
      )}
    </div>
  )
}
