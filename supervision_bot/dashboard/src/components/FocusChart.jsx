import React from 'react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'

export function FocusLineChart({ snapshots }) {
  const data = (snapshots ?? []).map(s => ({
    minute: s.minute_mark,
    score: Math.round(s.writing_score ?? 0),
    face: s.face_present ? 1 : 0,
  }))

  return (
    <div className="bg-slate-800 rounded-2xl p-6 shadow-lg">
      <h2 className="text-lg font-semibold text-slate-200 mb-4">本次专注曲线</h2>
      {data.length === 0 ? (
        <p className="text-slate-500 text-sm text-center py-8">等待数据...</p>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="minute" stroke="#94a3b8" tick={{ fontSize: 11 }}
              label={{ value: '分钟', position: 'insideRight', offset: 0, fill: '#94a3b8', fontSize: 11 }} />
            <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} domain={[0, 100]} />
            <Tooltip
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
              labelStyle={{ color: '#94a3b8' }} itemStyle={{ color: '#38bdf8' }} />
            <ReferenceLine y={50} stroke="#475569" strokeDasharray="4 4" />
            <Line type="monotone" dataKey="score" stroke="#38bdf8" strokeWidth={2}
              dot={false} name="书写活跃度" />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

export function WeekBarChart({ history }) {
  const data = (history ?? []).map(s => ({
    date: new Date(s.started_at).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }),
    minutes: Math.round((s.total_focus_seconds ?? 0) / 60),
    rounds: s.rounds_completed ?? 0,
  }))

  return (
    <div className="bg-slate-800 rounded-2xl p-6 shadow-lg">
      <h2 className="text-lg font-semibold text-slate-200 mb-4">7天专注记录</h2>
      {data.length === 0 ? (
        <p className="text-slate-500 text-sm text-center py-8">暂无历史数据</p>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 11 }} />
            <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
              labelStyle={{ color: '#94a3b8' }} itemStyle={{ color: '#818cf8' }} />
            <Bar dataKey="minutes" fill="#818cf8" radius={[4, 4, 0, 0]} name="专注分钟" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
