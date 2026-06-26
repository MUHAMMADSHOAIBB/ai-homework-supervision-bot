const api = require('../../utils/api')
const { t } = require('../../utils/i18n')

Page({
  data: {
    childName: '小明',
    grade: '四年级',
    connected: false,
    baseUrl: '',
    lang: 'zh',
    // translated strings
    menuItems: [],
  },

  onLoad() {
    const app = getApp()
    this.setData({
      childName: app.globalData.childName,
      baseUrl: app.globalData.baseUrl,
      lang: app.globalData.lang,
    })
    this._applyLang()
    api.getHealth()
      .then(() => this.setData({ connected: true }))
      .catch(() => this.setData({ connected: false }))
  },

  onShow() {
    const app = getApp()
    const lang = app.globalData.lang
    if (lang !== this.data.lang) {
      this.setData({ lang })
      this._applyLang()
    }
    this.setData({ childName: app.globalData.childName })
  },

  _applyLang() {
    const app = getApp()
    const lang = app.globalData.lang
    const isZh = lang === 'zh'
    this.setData({
      grade: isZh ? '四年级' : 'Grade 4',
      menuItems: t('menu'),
    })
  },

  // ── Menu handlers ──────────────────────────────────────────────────────────

  goParent() {
    wx.navigateTo({ url: '/pages/parent/parent' })
  },

  toggleLang() {
    const app = getApp()
    const newLang = app.globalData.lang === 'zh' ? 'en' : 'zh'
    app.globalData.lang = newLang
    wx.setStorageSync('lang', newLang)
    // Tell backend to switch voice language too
    api.setLanguage(newLang).catch(() => {})
    this.setData({ lang: newLang })
    this._applyLang()
    wx.showToast({
      title: newLang === 'en' ? 'Switched to English' : '已切换到中文',
      icon: 'success',
      duration: 1500,
    })
  },

  editName() {
    wx.showModal({
      title: t('editNameTitle'),
      editable: true,
      placeholderText: t('editNamePlaceholder'),
      success: res => {
        if (res.confirm && res.content && res.content.trim()) {
          const app = getApp()
          app.globalData.childName = res.content.trim()
          this.setData({ childName: res.content.trim() })
          wx.showToast({ title: '✅', icon: 'none' })
        }
      },
    })
  },

  openReminders() {
    wx.showToast({ title: t('lang') === 'en' ? 'Coming soon' : '即将推出', icon: 'none' })
  },

  openGoals() {
    wx.showToast({ title: t('lang') === 'en' ? 'Coming soon' : '即将推出', icon: 'none' })
  },

  openAbout() {
    wx.showModal({
      title: 'AI Homework Supervision Bot',
      content: 'Version 1.0\nBackend: FastAPI + DeepSeek AI\nCV: MediaPipe + YOLO\nBuilt for Nanjing Company',
      showCancel: false,
    })
  },
})
