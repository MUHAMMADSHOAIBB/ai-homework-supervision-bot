const api = require('../../utils/api')
const { t } = require('../../utils/i18n')
const { fmtTimer } = require('../../utils/format')

const PHASE_DURATION = { PREPARE: 30, FOCUS: 25 * 60, BREAK: 5 * 60, RESUME_CHECK: 30 }
const PHASE_ORDER = ['PREPARE', 'FOCUS', 'BREAK', 'RESUME_CHECK', 'COMPLETE']

Page({
  data: {
    connected: false,
    sessionActive: false,
    pomodoroState: 'IDLE',
    stateLabel: '',
    childName: '小明',
    timeDisplay: '25:00',
    roundNumber: 1,
    totalRounds: 4,
    focusMinutes: 25,
    progress: 0,
    phases: [],
    aiMessage: '',
    showAlert: false,
    currentAlert: '',
    focusScore: 0,
    frameUrl: '',
    showCamera: false,
    // i18n strings bound to WXML
    i_parentBtn:    '家长端 →',
    i_skipBtn:      '放弃本轮',
    i_alertTitle:   '温和提醒',
    i_alertOk:      '知道了',
    i_rewardsTitle: '完成奖励',
    i_rewardsSub:   '完成本轮即可获得',
    i_lbl1: '专注分数', i_lbl2: '当前轮次', i_lbl3: '剩余时间',
    i_btnText:      '开始学习',
    i_offline:      '',
    i_goal:         '目标 25 分钟',
    laptopMuted: false,
    // Chat panel
    showChat: false,
    chatMessages: [],
    chatInput: '',
    chatLoading: false,
    scrollId: '',
    i_chatTitle: '和 AI 聊聊',
    i_chatPlaceholder: '问问 AI 老师…',
    isSpeaking: false,
  },

  _pollTimer: null,
  _frameTimer: null,
  _phaseStart: 0,
  _lastState: '',
  _lastEventId: '',
  _audioCtx: null,
  _lastSpokenAlert: '',
  _msgId: 0,

  onLoad() {
    const app = getApp()
    this.setData({ childName: app.globalData.childName })
    this._applyLang()
    this._poll()
    this._pollTimer = setInterval(() => this._poll(), 2000)
    this._frameTimer = setInterval(() => this._refreshFrame(), 500)
    this._refreshFrame()
  },

  onShow() {
    this._applyLang()
    this._poll()
    this._refreshFrame()
  },

  onUnload() {
    clearInterval(this._pollTimer)
    clearInterval(this._frameTimer)
    if (this._audioCtx) { try { this._audioCtx.destroy() } catch(e){} }
  },

  _refreshFrame() {
    if (!this.data.connected) return
    this.setData({ frameUrl: api.cameraFrameUrl(), showCamera: true })
  },

  _speakText(text) {
    if (!text) return
    // Stop anything currently playing before starting new TTS
    if (this._audioCtx) {
      try { this._audioCtx.stop() } catch(e) {}
    }
    const lang = getApp().globalData.lang === 'zh' ? 'zh_CN' : 'en_US'
    wx.textToSpeech({
      lang,
      tts: true,
      content: text,
      success: res => {
        if (!this._audioCtx) {
          this._audioCtx = wx.createInnerAudioContext()
        }
        this._audioCtx.src = res.filePath
        this._audioCtx.onPlay(() => this.setData({ isSpeaking: true }))
        this._audioCtx.onEnded(() => this.setData({ isSpeaking: false }))
        this._audioCtx.onError(() => this.setData({ isSpeaking: false }))
        this._audioCtx.onStop(() => this.setData({ isSpeaking: false }))
        this._audioCtx.play()
      },
      fail: () => {},
    })
  },

  stopSpeak() {
    if (this._audioCtx) {
      try { this._audioCtx.stop() } catch(e) {}
    }
    this.setData({ isSpeaking: false })
  },

  _applyLang() {
    const phaseNames = t('phases')
    const phases = [
      { id: 'PREPARE',      icon: '🍅', name: phaseNames[0] },
      { id: 'FOCUS',        icon: '📖', name: phaseNames[1] },
      { id: 'remind',       icon: '🔔', name: phaseNames[2], virtual: true },
      { id: 'BREAK',        icon: '☕', name: phaseNames[3] },
      { id: 'RESUME_CHECK', icon: '✅', name: phaseNames[4] },
      { id: 'COMPLETE',     icon: '🎉', name: phaseNames[5] },
    ]
    const isActive = this.data.sessionActive
    this.setData({
      phases,
      i_parentBtn:    t('parentBtn'),
      i_skipBtn:      t('skipRound'),
      i_alertTitle:   t('alertTitle'),
      i_alertOk:      t('alertOk'),
      i_rewardsTitle: t('rewardsTitle'),
      i_rewardsSub:   t('rewardsSub'),
      i_lbl1: t('scoreLbl1'), i_lbl2: t('scoreLbl2'), i_lbl3: t('scoreLbl3'),
      i_btnText:      isActive ? t('btnStop') : t('btnStart'),
      i_offline:      t('offline'),
      i_chatTitle:       t('chatTitle'),
      i_chatPlaceholder: t('chatPlaceholder'),
      aiMessage:      this.data.sessionActive ? this.data.aiMessage : t('aiDefault'),
    })
    // Update goal text with current focusMinutes
    const fm = this.data.focusMinutes || 25
    this.setData({ i_goal: t('goalMin').replace('%d', fm) })
  },

  async _poll() {
    try {
      const session = await api.getSession()
      const state = session.pomodoro_state || 'IDLE'

      if (state !== this._lastState) {
        this._phaseStart = Date.now()
        this._lastState = state
      }

      const phaseElapsed  = (Date.now() - this._phaseStart) / 1000
      const phaseDuration = PHASE_DURATION[state] || 25 * 60
      const remaining     = Math.max(0, phaseDuration - phaseElapsed)
      const progress      = Math.min(1, phaseElapsed / phaseDuration)
      const active        = !['IDLE', 'COMPLETE'].includes(state)
      const stateLabels   = t('stateLabels')
      const phaseNames    = t('phases')

      const phases = [
        { id: 'PREPARE',      icon: '🍅', name: phaseNames[0] },
        { id: 'FOCUS',        icon: '📖', name: phaseNames[1] },
        { id: 'remind',       icon: '🔔', name: phaseNames[2], virtual: true },
        { id: 'BREAK',        icon: '☕', name: phaseNames[3] },
        { id: 'RESUME_CHECK', icon: '✅', name: phaseNames[4] },
        { id: 'COMPLETE',     icon: '🎉', name: phaseNames[5] },
      ].map(p => ({
        ...p,
        active: p.id === state,
        done: !p.virtual && PHASE_ORDER.indexOf(p.id) < PHASE_ORDER.indexOf(state),
      }))

      const focusMinutes = Math.round(phaseDuration / 60)

      this.setData({
        connected: true,
        frameUrl: api.cameraFrameUrl(),
        showCamera: true,
        sessionActive: active,
        pomodoroState: state,
        stateLabel: stateLabels[state] || state,
        childName: session.child_name || '小明',
        timeDisplay: fmtTimer(remaining),
        roundNumber: session.round_number || 1,
        focusMinutes,
        i_goal: t('goalMin').replace('%d', focusMinutes),
        i_btnText: active ? t('btnStop') : t('btnStart'),
        progress,
        phases,
        focusScore: Math.round(session.focus_score_current || 0),
      })

      this._drawRing(progress, state)

      if (active && session.session_id) {
        this._loadLatestAlert(session.session_id)
      }
      api.ttsStatus().then(s => this.setData({ laptopMuted: !!s.muted })).catch(() => {})
    } catch (e) {
      this.setData({ connected: false })
    }
  },

  async _loadLatestAlert(sessionId) {
    try {
      const events = await api.getEvents(sessionId)
      if (!events.length) return
      const last = events[events.length - 1]
      if (last.id === this._lastEventId) return
      if (['good_focus'].includes(last.event_type)) return
      this._lastEventId = last.id
      const alertMsgs = t('alertMsgs')
      const msg = alertMsgs[last.event_type] || (t('alertTitle') + '~')
      this.setData({ showAlert: true, currentAlert: msg })
      if (msg !== this._lastSpokenAlert) {
        this._lastSpokenAlert = msg
        this._speakText(msg)
      }
    } catch (e) {}
  },

  _drawRing(progress, state) {
    const sys  = wx.getWindowInfo()
    const size = Math.round(240 * sys.windowWidth / 750)
    const cx = size / 2, cy = size / 2, r = size * 0.40
    const ctx  = wx.createCanvasContext('timerRing', this)
    ctx.clearRect(0, 0, size, size)
    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.setStrokeStyle('#e8f5e0')
    ctx.setLineWidth(Math.round(size * 0.065))
    ctx.stroke()
    if (progress > 0.01) {
      ctx.beginPath()
      ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * progress)
      ctx.setStrokeStyle(state === 'BREAK' ? '#36cfc9' : '#52c41a')
      ctx.setLineWidth(Math.round(size * 0.065))
      ctx.setLineCap('round')
      ctx.stroke()
    }
    ctx.draw()
  },

  async onStartStop() {
    const app = getApp()
    if (this.data.sessionActive) {
      wx.showModal({
        title: t('stopConfirmTitle'),
        content: t('stopConfirmContent'),
        success: async res => {
          if (!res.confirm) return
          wx.showLoading({ title: '...' })
          try {
            await api.stopSession()
            app.globalData.sessionId = null
            this.setData({
              sessionActive: false, pomodoroState: 'IDLE',
              timeDisplay: '25:00', progress: 0, showAlert: false,
              i_btnText: t('btnStart'),
              aiMessage: t('aiDefault'),
            })
            wx.showToast({ title: t('stoppingToast'), icon: 'success' })
          } catch (e) {
            wx.showToast({ title: '❌', icon: 'none' })
          }
          wx.hideLoading()
        },
      })
    } else {
      wx.showLoading({ title: '...' })
      try {
        const res = await api.startSession(app.globalData.childName, app.globalData.childAge)
        app.globalData.sessionId = res.session_id
        this._phaseStart = Date.now()
        this._lastState  = ''
        const greet = await api.greet().catch(() => null)
        const greeting = greet ? greet.greeting : t('aiDefault')
        wx.hideLoading()
        this.setData({
          sessionActive: true,
          i_btnText: t('btnStop'),
          aiMessage: greeting,
          showAlert: false,
        })
        this._speakText(greeting)
        wx.showToast({ title: t('startingToast'), icon: 'success' })
      } catch (e) {
        wx.hideLoading()
        wx.showToast({ title: t('connectFail'), icon: 'error' })
      }
    }
  },

  dismissAlert() { this.setData({ showAlert: false, currentAlert: '' }) },

  async toggleLaptopMute() {
    try {
      if (this.data.laptopMuted) {
        await api.ttsUnmute()
        this.setData({ laptopMuted: false })
      } else {
        await api.ttsMute()
        this.setData({ laptopMuted: true })
      }
    } catch (e) {}
  },

  goToParent() { wx.navigateTo({ url: '/pages/parent/parent' }) },

  // ── AI Chat ──────────────────────────────────────────────────────────────

  openChat() {
    this.setData({ showChat: true })
  },

  closeChat() {
    this.setData({ showChat: false, chatInput: '' })
  },

  onChatInput(e) {
    this.setData({ chatInput: e.detail.value })
  },

  async sendChat() {
    const text = this.data.chatInput.trim()
    if (!text || this.data.chatLoading) return

    const msgs = this.data.chatMessages
    const uid  = ++this._msgId
    msgs.push({ id: uid, role: 'user', text })
    this.setData({
      chatMessages: msgs,
      chatInput: '',
      chatLoading: true,
      scrollId: 'msg' + uid,
    })

    try {
      const res = await api.chat(text)
      const reply = res.reply || '...'
      const aid = ++this._msgId
      const updated = this.data.chatMessages
      updated.push({ id: aid, role: 'ai', text: reply })
      this.setData({
        chatMessages: updated,
        chatLoading: false,
        aiMessage: reply,
        scrollId: 'msg' + aid,
      })
      this._speakText(reply)
    } catch (e) {
      const updated = this.data.chatMessages
      updated.push({ id: Date.now(), role: 'ai', text: t('connectFail') })
      this.setData({ chatMessages: updated, chatLoading: false })
    }
  },
})
