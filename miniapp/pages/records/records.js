const api = require('../../utils/api')
const { t } = require('../../utils/i18n')
const { fmtMinSec } = require('../../utils/format')

Page({
  data: {
    sessions: [],
    i_title: '📋 学习记录',
    i_noRecords: '还没有学习记录',
    i_noRecordsSub: '完成第一次学习后这里会显示记录',
    i_focusTime: '专注时长',
    i_rounds: '番茄钟',
    i_distracts: '分心次数',
  },

  onShow() {
    this._applyLang()
    this._load()
  },

  _applyLang() {
    this.setData({
      i_title:        '📋 ' + t('recordsTitle'),
      i_noRecords:    t('noRecords'),
      i_noRecordsSub: t('noRecordsSub'),
      i_focusTime:    t('focusTime'),
      i_rounds:       t('rounds'),
      i_distracts:    t('distracts'),
    })
  },

  async _load() {
    try {
      const history = await api.getHistory(1)
      const lang = getApp().globalData.lang
      const isZh = lang === 'zh'
      const sessions = history.map(s => {
        const score = Math.round(s.focus_score_avg || 0)
        const d = new Date(s.started_at)
        const counts = s.event_counts || {}
        const distracts = (counts.distracted_gaze || 0) + (counts.phone_detected || 0) + (counts.out_of_seat || 0)
        const dateStr = isZh
          ? `${d.getMonth()+1}月${d.getDate()}日`
          : `${d.getMonth()+1}/${d.getDate()}`
        return {
          id: s.id,
          dateStr,
          score,
          scoreColor: score >= 80 ? '#52c41a' : score >= 50 ? '#fa8c16' : '#ff4d4f',
          focusTime: fmtMinSec(s.total_focus_seconds || 0),
          rounds: s.rounds_completed || 0,
          distracts,
        }
      }).reverse()
      this.setData({ sessions })
    } catch (e) {}
  },
})
