const app = getApp()

function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: app.globalData.baseUrl + path,
      method: options.method || 'GET',
      data: options.data || {},
      header: { 'Content-Type': 'application/json', ...(options.header || {}) },
      success: res => {
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data)
        else reject(new Error('HTTP ' + res.statusCode))
      },
      fail: err => reject(err),
    })
  })
}

module.exports = {
  getSession:   ()           => request('/session/current'),
  getHealth:    ()           => request('/health'),
  startSession: (name, age)  => request('/session/start',    { method: 'POST', data: { child_name: name, child_age: age } }),
  stopSession:  ()           => request('/session/stop',     { method: 'POST' }),
  getEvents:    (id)         => request(`/session/${id}/events`),
  getSnapshots: (id)         => request(`/session/${id}/snapshots`),
  getHistory:   (childId)    => request(`/history/${childId}`),
  chat:         (msg)        => request('/chat',             { method: 'POST', data: { message: msg } }),
  greet:        ()           => request('/coach/greet',      { method: 'POST' }),
  ttsStatus:    ()           => request('/tts/status'),
  ttsStop:      ()           => request('/tts/stop',   { method: 'POST' }),
  ttsMute:      ()           => request('/tts/mute',   { method: 'POST' }),
  ttsUnmute:    ()           => request('/tts/unmute', { method: 'POST' }),
  setLanguage:  (lang)       => request('/session/language', { method: 'POST', data: { lang } }),
  // Returns URL string (not a fetch) — append to <image src>
  cameraFrameUrl: () => app.globalData.baseUrl + '/camera/frame?t=' + Date.now(),
  ttsLatestUrl:   () => app.globalData.baseUrl + '/tts/latest?t=' + Date.now(),
}
