## 1. Product Background

An AI focus learning robot built around the Pomodoro Technique, guided by child attention development theory. It uses visual perception, multimodal interaction, and intelligent guidance to provide real-time supervision of the learning process, dynamic feedback, and long-term habit formation. The core function is supervising children while they do homework and study. Problems it solves:

1. Parents can't stay with children continuously to monitor them, making it hard to catch distraction in real time.
2. Children have weak self-management skills and easily space out, get distracted, play with their phone, or leave their seat frequently.
3. Traditional Pomodoro tools only offer time management — they lack real-time awareness of learning state and dynamic guidance.
4. Parents can only see learning outcomes, not how focus levels and behavior changed throughout the session.

The final product aims to be an AI learning companion system with a **child-side** and **parent-side** component used together.

The child-side comes in two forms:
- A **hardware learning bot** placed on the desk — uses a camera, microphone, speaker, and display screen to accompany the child while studying.
- A **lightweight mini-program or App** that uses the phone or tablet camera to run Pomodoro sessions, detect learning state, and deliver AI reminders.

While the child studies, the system manages learning rhythm via the Pomodoro flow, detecting whether the child is seated, doing homework, spacing out, using a phone, or slumping with fatigue — and responds with voice prompts, expressions, or an animated avatar.

The parent-side is a mini-program or App showing a study dashboard: whether the child is currently focused, how long they've been studying, how many Pomodoro rounds they've completed today, how many times they got distracted, and how focus has trended over time.

---

## 2. Software Modules

| Feature | Definition | Notes |
| :--- | :--- | :--- |
| Real-time state recognition | Continuously detects and outputs states: in-seat/out-of-seat, looking at desk/distracted, writing activity, posture, phone use, fatigue risk | |
| Pomodoro flow | Prepare, Focus, Break, Resume, Complete | |
| Rules engine | Events and thresholds trigger corresponding actions | |
| Script generation | Rules provide intent; the agent generates the final spoken script | |
| Voice output (TTS) | Converts scripts to audio | |
| Facial expression state machine | Generates expressions based on current action and state machine state | |
| Parent-side display | View focus duration, interruption events, posture trends, session summaries | |
| Data storage & privacy | Local, minimal storage; parent authorization required before use; history can be deleted | |

---

## 3. Flow

Real-time recognition → Pomodoro state machine → Rules engine → Script generation → TTS → TFT expression feedback → Parent-side display

### Pomodoro State Machine

| State | Entry Condition | Actions | Exit Condition |
| :--- | :--- | :--- | :--- |
| IDLE | User hasn't started | Show standby expression, wait for start | Tap start or voice wake |
| PREPARE | 1–2 minutes before study begins | Guide child to sit properly, prepare stationery, confirm desk ROI | Child is ready or prep time expires |
| FOCUS | Entering focus phase | Timer running, recognition active, light feedback | Focus duration reached or serious interruption |
| BREAK | Normal rest | Relaxation script, rest expression, disable intervention recognition | Break duration expires |
| RESUME_CHECK | Post-break wrap-up | Check whether child has returned to desk | If back at desk, re-enter FOCUS |
| COMPLETE | Round/session ends | Summary script, parent-side digest | Session ends |

### Focus Phase Flow

~~~
┌───────────────┐
│ Focus State   │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Camera Feed   │
└───────┬───────┘
        │
        ▼
┌───────────────────────────────────┐
│     Parallel Perception Module    │
├──────────┬──────────┬─────────────┤
│ ROI      │Landmarks │Object Det.  │
│ Extraction│Pose/Face│Phone/Book/  │
│          │          │Person       │
├──────────┴──────────┴─────────────┤
│          Optical Flow Analysis    │
│       Writing Activity Score      │
└─────────────────┬─────────────────┘
                  │
                  ▼
┌──────────────────────────┐
│     Feature Aggregation  │
├──────────────────────────┤
│ Head Pose                │
│ Gaze Direction           │
│ Eye Closure Ratio        │
│ Hand Presence            │
│ Writing Activity         │
│ Phone Presence           │
│ Seat Presence            │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│    Focus Rule Engine     │
└─────┬─────┬─────┬─────┬──┘
      │     │     │     │
      ▼     ▼     ▼     ▼

Phone     Fatigue          Out-of-   Distraction     Posture
Detection (drowsy /        Seat      Detection       Detection
          over-focused)    Detection (pen idle,      (head too high,
                                     face off-       eyes too close,
                                     camera,         crossed legs...)
                                     eyes closed)
      │     │     │     │
      └──┬──┴──┬──┴──┬──┘
         │     │     │
         ▼     ▼     ▼

      Alert    State Log    Animation Feedback
~~~

### Break Phase Flow

~~~
┌───────────────┐
│ Break State   │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Camera Feed   │
└───────┬───────┘
        │
        ▼
┌───────────────────────────────────┐
│     Parallel Perception Module    │
├──────────┬──────────┬─────────────┤
│ ROI      │Landmarks │Object Det.  │
│ Extraction│Pose/Face│Phone/Book/  │
│          │          │Person       │
├──────────┴──────────┴─────────────┤
│          Optical Flow Analysis    │
│         Body Activity Score       │
└─────────────────┬─────────────────┘
                  │
                  ▼
┌──────────────────────────┐
│     Feature Aggregation  │
├──────────────────────────┤
│ Body Motion              │
│ Seat Presence            │
│ Distance To Screen       │
│ Writing Activity         │
│ Break Duration           │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│    Break Rule Engine     │
└─────┬─────┬─────┬─────┬──┘
      │     │     │     │
      ▼     ▼     ▼     ▼

Continue    Sitting      Too Close    Break
Studying    Too Long     to Screen    Over
      │     │     │     │
      └──┬──┴──┬──┴──┬──┘
         │     │     │
         ▼     ▼     ▼

      Break reminder
      Get up and move reminder
      Return to focus mode
      State log
~~~
