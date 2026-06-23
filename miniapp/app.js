App({
  globalData: {
    baseUrl: 'http://127.0.0.1:8000',
    childName: '小明',
    childAge: 10,
    sessionId: null,
    lang: 'zh',
  },
  onLaunch() {
    // Restore saved language
    const saved = wx.getStorageSync('lang')
    if (saved) this.globalData.lang = saved
  },
})
