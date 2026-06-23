const api = require('../../utils/api')
const { t } = require('../../utils/i18n')
// api.cameraFrameUrl() used for live preview
const { fmtMinSec, fmtTime } = require('../../utils/format')

const EVENT_COLOR = {
  phone_detected:'#ff4d4f', out_of_seat:'#ff7a45', distracted_gaze:'#ffa940',
  writing_idle:'#ffc53d', fatigue_drowsy:'#ff9c6e', bad_posture_close:'#ffa940',
  bad_posture_slouch:'#ffc53d', good_focus:'#52c41a', talking:'#69b1ff',
}

Page({
  data: {
    connected: false,
    childName: '小明',
    grade: '四年级',
    sessionActive: false,
    stateLabel: '',
    roundInfo: '–',
    todayFocus: '–',
    todayRounds: '–',
    distractCount: '–',
    postureStatus: '–',
    postureKey: 'good',
    events: [],
    weekData: [],
    weekAvg: '–',
    // i18n
    i_title: '监督 Bot · 家长端',
    i_backBtn: '← 返回',
    i_overview: '今日概览',
    i_eventLog: '事件（今日）',
    i_seeAll: '查看全部 ›',
    i_weekTrend: '本周趋势',
    i_weekAvgLabel: '本周平均',
    i_noEvents: '暂无事件记录',
    i_offline: '⚠️ 未连接后端',
    i_privacy: ['隐私模式', '开启中', '摄像头权限', '已授权', '数据可见', '仅家长'],
    frameUrl: '',
    showCamera: false,
    statNames: ['今日专注', '番茄轮数', '分心事件', '坐姿/疲劳'],
    statTargets: ['目标 2 小时', '目标 6 轮', '次', ''],
  },

  _pollTimer: null,
  _frameTimer: null,

  onLoad() {
    this._applyLang()
    this._refresh()
    this._pollTimer = setInterval(() => this._refresh(), 3000)
    this._frameTimer = setInterval(() => this._refreshFrame(), 2000)
    this._refreshFrame()
  },
  onUnload() { clearInterval(this._pollTimer); clearInterval(this._frameTimer) },
  onShow()   { this._applyLang(); this._refresh(); this._refreshFrame() },

  _refreshFrame() {
    if (!this.data.connected) return
    this.setData({ frameUrl: api.cameraFrameUrl(), showCamera: true })
  },

  _applyLang() {
    const sn = t('statNames')
    const st = t('statTargets')
    this.setData({
      i_title:        t('parentTitle'),
      i_backBtn:      t('backBtn'),
      i_overview:     t('todayOverview'),
      i_eventLog:     t('eventLog'),
      i_seeAll:       t('seeAll'),
      i_weekTrend:    t('weekTrend'),
      i_weekAvgLabel: t('weekAvgLabel'),
      i_noEvents:     t('noEvents'),
      i_offline:      t('offline'),
      i_privacy:      t('privacy'),
      statNames:  sn,
      statTargets: st,
    })
    // Re-label existing events
    this._relabelEvents()
  },

  _relabelEvents() {
    const alertMsgs = t('alertMsgs')
    const events = this.data.events.map(e => ({
      ...e,
      label: alertMsgs[e.event_type]
        ? alertMsgs[e.event_type].split('，')[0].split(',')[0].slice(0, 10)
        : e.event_type,
    }))
    this.setData({ events })
  },

  async _refresh() {
    try {
      const session = await api.getSession()
      const state   = session.pomodoro_state || 'IDLE'
      const active  = !['IDLE', 'COMPLETE'].includes(state)
      const statusMap = t('statusMap')
      const lang = getApp().globalData.lang
      const isZh = lang === 'zh'

      this.setData({
        connected: true,
        frameUrl: api.cameraFrameUrl(),
        showCamera: true,
        childName: session.child_name || '小明',
        grade: isZh ? '四年级' : 'Grade 4',
        sessionActive: active,
        stateLabel: statusMap[state] || state,
        roundInfo: isZh
          ? `第 ${session.round_number || 1}/4 轮`
          : `Round ${session.round_number || 1}/4`,
        focusScore: Math.round(session.focus_score_current || 0),
      })

      if (session.session_id) {
        const [events, snaps] = await Promise.all([
          api.getEvents(session.session_id),
          api.getSnapshots(session.session_id).catch(() => []),
        ])
        this._processEvents(events, snaps)
      }

      const history = await api.getHistory(1).catch(() => [])
      this._processHistory(history)

    } catch (e) {
      this.setData({ connected: false })
    }
  },

  _processEvents(events, snaps) {
    const distractions = events.filter(e =>
      ['distracted_gaze', 'out_of_seat', 'phone_detected'].includes(e.event_type)).length
    const postureBad = events.filter(e =>
      ['bad_posture_close', 'bad_posture_slouch', 'fatigue_drowsy'].includes(e.event_type)).length

    const totalFocusSec = snaps.length ? snaps[snaps.length - 1].minute_mark * 60 : 0
    const rounds = events.filter(e => e.event_type === 'good_focus').length

    const alertMsgs = t('alertMsgs')
    const lang = getApp().globalData.lang
    const isZh = lang === 'zh'
    const postureKey = postureBad === 0 ? 'good' : postureBad < 3 ? 'ok' : 'bad'
    const postureMap = isZh
      ? { good: '良好', ok: '一般', bad: '较差' }
      : { good: 'Good', ok: 'Fair', bad: 'Poor' }

    const timeline = [...events]
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
      .slice(0, 8)
      .map(e => ({
        ...e,
        label: (alertMsgs[e.event_type] || e.event_type).split('，')[0].split(',')[0].slice(0, 12),
        color: EVENT_COLOR[e.event_type] || '#8c8c8c',
        timeStr: fmtTime(e.timestamp),
      }))

    this.setData({
      todayFocus:   fmtMinSec(totalFocusSec),
      todayRounds:  String(rounds || 0),
      distractCount: String(distractions),
      postureStatus: postureMap[postureKey],
      postureKey,
      events: timeline,
    })
  },

  _processHistory(history) {
    if (!history.length) return
    const lang = getApp().globalData.lang
    const isZh = lang === 'zh'
    const days = isZh ? ['日','一','二','三','四','五','六'] : ['Su','Mo','Tu','We','Th','Fr','Sa']
    const now  = new Date()
    const grid = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(now)
      d.setDate(now.getDate() - (6 - i))
      return { day: days[d.getDay()], sec: 0, dateStr: d.toDateString() }
    })
    history.forEach(s => {
      const ds = new Date(s.started_at).toDateString()
      const slot = grid.find(g => g.dateStr === ds)
      if (slot) slot.sec += (s.total_focus_seconds || 0)
    })
    const maxSec = Math.max(...grid.map(g => g.sec), 1)
    const totalSec = grid.reduce((a, g) => a + g.sec, 0)

    const weekData = grid.map(g => ({
      day: g.day,
      heightPct: Math.round((g.sec / maxSec) * 100),
      label: g.sec > 0 ? fmtMinSec(g.sec) : '',
      color: g.sec > 0 ? '#52c41a' : '#e8f5e0',
    }))
    this.setData({ weekData, weekAvg: fmtMinSec(totalSec / 7) })
  },

  goBack() { wx.navigateBack() },
})
