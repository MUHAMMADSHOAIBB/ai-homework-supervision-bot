import re
import os

with open('dashboard/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Add lang-btn
html = html.replace(
    '<div class="header-right">\n    <input id="child-name"',
    '<div class="header-right">\n    <button id="lang-btn" class="btn" style="background:#475569; margin-right: 10px;">English</button>\n    <input id="child-name"'
)

# Replace static IDs
html = html.replace('<h1>📚 AI 作业监督助手</h1>', '<h1 id="main-title">📚 AI 作业监督助手</h1>')
html = html.replace('<h2>事件记录 <span id="ev-count"', '<h2 id="ev-log-title">事件记录 <span id="ev-count"')
html = html.replace('<h2>本次专注曲线</h2>', '<h2 id="focus-curve-title">本次专注曲线</h2>')
html = html.replace('<h2>7天专注记录</h2>', '<h2 id="history-title">7天专注记录</h2>')

# Replace the script tag start to add i18n
script_start = """<script>
const BASE = 'http://127.0.0.1:8000';

// ── i18n ──────────────────────────────────────────────────────────────────────
let currentLang = 'zh';
const I18N = {
  zh: {
    mainTitle: '📚 AI 作业监督助手',
    apiWait: '后端未连接 — 请运行 python main.py',
    apiOk: '后端已连接 (localhost:8000)',
    childName: '孩子姓名',
    startLearning: '开始学习',
    stopLearning: '停止学习',
    studyStatus: ' 的学习状态',
    noPerson: '未检测到人',
    curPhase: '当前阶段',
    round: '第几轮',
    focusScore: '专注分数',
    recentEvent: '最近事件: ',
    evLog: '事件记录',
    noEvents: '暂无事件',
    focusCurve: '本次专注曲线',
    waitData: '等待数据...',
    historyTitle: '7天专注记录',
    noHistory: '暂无历史数据',
    minute: '分钟',
    summaryTitle: '🎉 本次学习总结',
    tomato: '番茄钟',
    focusTime: '专注时长',
    face: '脸部:',
    phone: '手机:',
    write: '书写:',
    state: '状态:',
    used: '已用:',
    yes: '✅ 是',
    no: '✅ 否',
    phoneAlert: '🚨 检测到手机！',
    distracted: '注意力分散',
    focusing: '专心学习中',
    stopFail: '停止失败: ',
    startFail: '无法连接后端。请先运行: python main.py --api-only',
    langBtn: 'English',
    states: {IDLE:'待机',PREPARE:'准备中',FOCUS:'专注中',BREAK:'休息中',RESUME_CHECK:'继续确认',COMPLETE:'完成'},
    events: {phone_detected:'手机使用',out_of_seat:'离开座位',distracted_gaze:'注意力分散',writing_idle:'停止书写',fatigue_drowsy:'疲劳',bad_posture_close:'距离过近',bad_posture_slouch:'坐姿不良',break_studying:'休息时学习',break_sedentary:'休息时久坐',good_focus:'优秀专注'},
    pri: {'3':'高','2':'中','1':'低'}
  },
  en: {
    mainTitle: '📚 AI Homework Supervisor',
    apiWait: 'Backend disconnected — Please run python main.py',
    apiOk: 'Backend connected (localhost:8000)',
    childName: "Child's Name",
    startLearning: 'Start Learning',
    stopLearning: 'Stop Learning',
    studyStatus: "'s Study Status",
    noPerson: 'No person detected',
    curPhase: 'Current Phase',
    round: 'Round',
    focusScore: 'Focus Score',
    recentEvent: 'Recent Event: ',
    evLog: 'Event Log',
    noEvents: 'No events',
    focusCurve: 'Focus Curve',
    waitData: 'Waiting for data...',
    historyTitle: '7-Day History',
    noHistory: 'No history',
    minute: 'Minutes',
    summaryTitle: '🎉 Study Summary',
    tomato: 'Pomodoro',
    focusTime: 'Focus Time',
    face: 'Face:',
    phone: 'Phone:',
    write: 'Write:',
    state: 'State:',
    used: 'Used:',
    yes: '✅ Yes',
    no: '✅ No',
    phoneAlert: '🚨 Phone detected!',
    distracted: 'Distracted',
    focusing: 'Focusing',
    stopFail: 'Stop failed: ',
    startFail: 'Cannot connect to backend. Please run: python main.py --api-only',
    langBtn: '中文',
    states: {IDLE:'Idle',PREPARE:'Preparing',FOCUS:'Focusing',BREAK:'Break',RESUME_CHECK:'Resume Check',COMPLETE:'Complete'},
    events: {phone_detected:'Phone Used',out_of_seat:'Out of Seat',distracted_gaze:'Distracted',writing_idle:'Stopped Writing',fatigue_drowsy:'Fatigue',bad_posture_close:'Too Close',bad_posture_slouch:'Slouching',break_studying:'Studying in Break',break_sedentary:'Sedentary in Break',good_focus:'Good Focus'},
    pri: {'3':'High','2':'Med','1':'Low'}
  }
};

function t(key, subkey) {
  if (subkey) return I18N[currentLang][key][subkey] || subkey;
  return I18N[currentLang][key] || key;
}

document.getElementById('lang-btn').addEventListener('click', () => {
  currentLang = currentLang === 'zh' ? 'en' : 'zh';
  document.getElementById('lang-btn').textContent = t('langBtn');
  document.getElementById('main-title').textContent = t('mainTitle');
  document.getElementById('child-name').placeholder = t('childName');
  
  // Refresh UI
  updateBtn();
  setApiStatus(apiOk);
  document.getElementById('ev-log-title').childNodes[0].nodeValue = t('evLog') + ' ';
  document.getElementById('focus-curve-title').textContent = t('focusCurve');
  document.getElementById('history-title').textContent = t('historyTitle');
  
  // Re-render components with new language
  const emptyMsgs = document.querySelectorAll('.empty-msg');
  if (emptyMsgs[0] && emptyMsgs[0].textContent.includes('暂无') || emptyMsgs[0] && emptyMsgs[0].textContent.includes('No events')) {
      emptyMsgs[0].textContent = t('noEvents');
  }
  if (emptyMsgs[1] && emptyMsgs[1].textContent.includes('等待') || emptyMsgs[1] && emptyMsgs[1].textContent.includes('Wait')) {
      emptyMsgs[1].textContent = t('waitData');
  }
  if (emptyMsgs[2] && emptyMsgs[2].textContent.includes('暂无') || emptyMsgs[2] && emptyMsgs[2].textContent.includes('No hist')) {
      emptyMsgs[2].textContent = t('noHistory');
  }
  
  // Force a re-fetch to re-render dynamic content
  fetchSession();
});

"""

html = re.sub(r"<script>\s*const BASE = 'http://127.0.0.1:8000';\n", script_start, html)

# Replace labels dictionaries
html = re.sub(r"const STATE_LABELS\s*=\s*\{.*?\};", "const STATE_LABELS = I18N[currentLang].states;", html)
html = re.sub(r"const EVENT_LABELS\s*=\s*\{.*?\};", "const EVENT_LABELS = I18N[currentLang].events;", html)
html = re.sub(r"const PRI_LABELS\s*=\s*\{.*?\};", "const PRI_LABELS = I18N[currentLang].pri;", html)

# Replace updateStatusCard hardcoded texts
html = html.replace(" + ' 的学习状态';", " + t('studyStatus');")
html = html.replace("STATE_LABELS[state]||state", "t('states', state)")
html = html.replace("STATE_LABELS[state]?state:'IDLE'", "I18N[currentLang].states[state]?state:'IDLE'")
html = html.replace("txt.textContent = '未检测到人';", "txt.textContent = t('noPerson');")
html = html.replace("txt.textContent = '🚨 检测到手机！';", "txt.textContent = t('phoneAlert');")
html = html.replace("txt.textContent = '注意力分散';", "txt.textContent = t('distracted');")
html = html.replace("txt.textContent = '专心学习中';", "txt.textContent = t('focusing');")
html = html.replace("evRow.textContent = '最近事件: '+(EVENT_LABELS[session.last_event]||session.last_event);", "evRow.textContent = t('recentEvent')+(t('events', session.last_event));")
html = html.replace("<div class=\"stat-lbl\">当前阶段</div>", "<div class=\"stat-lbl\" id=\"lbl-phase\">当前阶段</div>")
html = html.replace("<div class=\"stat-lbl\">第几轮</div>", "<div class=\"stat-lbl\" id=\"lbl-round\">第几轮</div>")
html = html.replace("<div class=\"stat-lbl\">专注分数</div>", "<div class=\"stat-lbl\" id=\"lbl-score\">专注分数</div>")

html = html.replace(
    "document.getElementById('stat-score').textContent = Math.round(session?.focus_score_current||0);",
    "document.getElementById('stat-score').textContent = Math.round(session?.focus_score_current||0);\n  document.getElementById('lbl-phase').textContent = t('curPhase');\n  document.getElementById('lbl-round').textContent = t('round');\n  document.getElementById('lbl-score').textContent = t('focusScore');"
)

# Timeline replacements
html = html.replace("tl.innerHTML='<p class=\"empty-msg\">暂无事件</p>';", "tl.innerHTML=`<p class=\"empty-msg\">${t('noEvents')}</p>`;")
html = html.replace("EVENT_LABELS[ev.event_type]||ev.event_type", "t('events', ev.event_type)")
html = html.replace("PRI_LABELS[pk]||pk", "t('pri', pk)")

# Line chart replacements
html = html.replace("wrap.innerHTML='<p class=\"empty-msg\">等待数据...</p>';", "wrap.innerHTML=`<p class=\"empty-msg\">${t('waitData')}</p>`;")
html = html.replace("<text class=\"axis\" x=\"${W/2}\" y=\"${H}\" text-anchor=\"middle\">分钟</text>", "<text class=\"axis\" x=\"${W/2}\" y=\"${H}\" text-anchor=\"middle\">${t('minute')}</text>")

# Bar chart replacements
html = html.replace("wrap.innerHTML='<p class=\"empty-msg\">暂无历史数据</p>';", "wrap.innerHTML=`<p class=\"empty-msg\">${t('noHistory')}</p>`;")

# Summary replacements
html = html.replace("EVENT_LABELS[k]||k", "t('events', k)")
html = html.replace("<h2>🎉 本次学习总结</h2>", "<h2>${t('summaryTitle')}</h2>")
html = html.replace("<div class=\"stat-lbl\">番茄钟</div>", "<div class=\"stat-lbl\">${t('tomato')}</div>")
html = html.replace("<div class=\"stat-lbl\">专注时长</div>", "<div class=\"stat-lbl\">${t('focusTime')}</div>")
html = html.replace("<div class=\"stat-lbl\">专注分数</div>", "<div class=\"stat-lbl\">${t('focusScore')}</div>")

# Live bar replacements
html = html.replace("<span><b>脸部:</b> ${live.face_present?'✅':'❌'}</span>", "<span><b>${t('face')}</b> ${live.face_present?'✅':'❌'}</span>")
html = html.replace("<span><b>手机:</b> ${live.phone_detected?'🚨 是':'✅ 否'}</span>", "<span><b>${t('phone')}</b> ${live.phone_detected?t('yes'):t('no')}</span>")
html = html.replace("<span><b>书写:</b> ${live.writing_score}</span>", "<span><b>${t('write')}</b> ${live.writing_score}</span>")
html = html.replace("<span><b>EAR:</b> ${live.ear_avg}</span>", "<span><b>EAR:</b> ${live.ear_avg}</span>")
html = html.replace("<span><b>状态:</b> ${STATE_LABELS[live.pomodoro_state]||live.pomodoro_state}</span>", "<span><b>${t('state')}</b> ${t('states', live.pomodoro_state)}</span>")
html = html.replace("<span><b>已用:</b> ${live.elapsed_seconds}s / 第${live.round_number}轮</span>", "<span><b>${t('used')}</b> ${live.elapsed_seconds}s / ${live.round_number}</span>")

# Api Status replacements
html = html.replace(
    "document.getElementById('api-status').innerHTML = ok\n    ? '<span class=\"dot-green\">●</span> 后端已连接 (localhost:8000)'\n    : '<span class=\"dot-red\">●</span> 后端未连接 — 请运行 python main.py';",
    "document.getElementById('api-status').innerHTML = ok\n    ? '<span class=\"dot-green\">●</span> ' + t('apiOk')\n    : '<span class=\"dot-red\">●</span> ' + t('apiWait');"
)

# Button Text
html = html.replace("btn.textContent='停止学习'", "btn.textContent=t('stopLearning')")
html = html.replace("btn.textContent='开始学习'", "btn.textContent=t('startLearning')")

# Alerts
html = html.replace("alert('停止失败: '+e.message);", "alert(t('stopFail')+e.message);")
html = html.replace("alert('无法连接后端。请先运行: python main.py --api-only');", "alert(t('startFail'));")

with open('dashboard/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("index.html patched successfully.")
