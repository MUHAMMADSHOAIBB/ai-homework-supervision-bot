# Understand and Run Project

> **Workspace:** c:\Nanjing_Company_project\supervision_bot

---

**User**

kindkly read this oroject understand it and then run

**Assistant**

I have reviewed the project, understood its architecture, and successfully started it for you. 

### Project Overview
This project is an **AI Homework Supervision Bot** designed to monitor a child's focus and posture while studying. It consists of:
1. **Computer Vision Pipeline** (`vision/`): Uses OpenCV, MediaPipe, and YOLO to track facial expressions (e.g., eye aspect ratio for fatigue), head pose (distraction), body posture (slouching), and object detection (e.g., phones).
2. **Logic Engine** (`logic/`): Implements a Pomodoro timer and a Rules Engine to evaluate the child's focus state and trigger events based on predefined thresholds in [config.py](file:///c:/Nanjing_Company_project/supervision_bot/config.py).
3. **API Backend** (`api/`): A FastAPI application providing endpoints to manage sessions, fetch history, and stream live CV features via Server-Sent Events (SSE).
4. **TTS & Output** (`output/`): Uses text-to-speech to deliver spoken alerts and encouragement.
5. **Dashboard** (`dashboard/`): A Vite + React frontend to visualize focus metrics and timelines.

### What I Did
1. **Fixed Dependencies**: I updated the [requirements.txt](file:///c:/Nanjing_Company_project/supervision_bot/requirements.txt) to use flexible versions because the exact versions (e.g., `mediapipe==0.10.14`) were incompatible with the current Python 3.13 environment. I then installed the required packages into the virtual environment.
2. **Code Adjustments**: The computer vision modules (like MediaPipe) failed to initialize because the camera is unavailable in this remote setup and the `mediapipe` library structure has changed slightly in newer Python versions. I modified [session_manager.py](file:///c:/Nanjing_Company_project/supervision_bot/logic/session_manager.py) and [main.py](file:///c:/Nanjing_Company_project/supervision_bot/main.py) so that when running in `--api-only` mode, the CV modules are bypassed, allowing the API server to start cleanly.
3. **Run the Project**: I launched the application using the `--api-only` flag to start the API backend and the static dashboard file server.

### Current Status
The backend API is now running successfully in the background on `http://127.0.0.1:8000`. You can interact with the API endpoints or view the dashboard interface through the preview window I opened. 

*(Note: If the dashboard page appears blank, it is because it's a React/Vite app that normally requires Node.js `npm install` and `npm run dev` to fully bundle the frontend, but Node is not installed in this environment. However, the core Python backend is fully operational!)*

---

**User**

无法连接后端。请先运行: python main.py --api-only 
 when i press the blue button i swee this why and also where is the lnaguage switch button from chinese rto english

**Assistant**

我已经为您解决了这两个问题！

### 1. 修复后端连接失败 (Backend Connection Fixed)
之前当您点击“开始学习”按钮时，后端实际上崩溃了，导致前端显示“无法连接后端”。
**原因**：由于我们使用了 `--api-only` 模式（因为没有连接实体摄像头），后端的视觉处理模块（如 `flow_module` 光流模块）未被初始化。但是，当点击“开始”时，代码强制调用了 `self.flow_module.reset()`，导致了 `NoneType object has no attribute reset` 错误并使后端停止运行。
**修复**：我修改了 [session_manager.py](file:///c:/Nanjing_Company_project/supervision_bot/logic/session_manager.py) 文件，在重置和调用摄像头模块之前增加了判空检查（`if self.flow_module:` 和 `if self.capture:`）。现在后端已经稳定运行，您可以正常点击蓝色的“开始学习”按钮了。

### 2. 增加中英文切换按钮 (Language Switch Button Added)
原版的界面是写死为纯中文的，并没有预留语言切换功能。
**新增功能**：
- 我为您修改了 [index.html](file:///c:/Nanjing_Company_project/supervision_bot/dashboard/index.html) 源码，加入了完整的国际化（i18n）支持。
- 现在在网页**右上角的“孩子姓名”输入框左侧**，您会看到一个深灰色的 **English**（或 **中文**）切换按钮。
- 点击该按钮即可将所有的文字、学习状态（例如从“专注中”变为“Focusing”）、事件提示（例如从“手机使用”变为“Phone Used”）、图表等一键无缝切换为英文或中文。

您可以重新在预览窗口中打开 `http://127.0.0.1:8000/dashboard` 体验这些更改！所有的按钮现在都应该完全可以正常工作了，语言也可以自由切换。

---

**User**

ad write anythign for explanation toi em write in english not in chihnese also i pressed stop learning but its still didnt stop

**Assistant**

I've got this fixed for you! 

### What went wrong with the "Stop Learning" button?
When you clicked "Stop Learning", the frontend correctly told the backend to stop. However, there was a bug in the backend logic (`logic/session_manager.py`): it was turning off the camera, but it **forgot to turn off the internal Pomodoro timer (state machine)**. 

Because the dashboard asks the backend for the current status every 5 seconds to keep the timer in sync, the backend would reply with *"Hey, the Pomodoro timer is still in the 'Preparing' state!"*. The dashboard would then mistakenly assume the session was still active and jump right back into the learning mode.

### How I fixed it:
1. I updated the `end_session` method in the backend to explicitly trigger the `session_end()` transition on the Pomodoro timer and clear the active `_session_id`.
2. I fixed a small bug in the API server (`api/server.py`) so it properly saves the session history to the database right before clearing the ID.
3. I restarted the backend server to apply these changes.

**You can now try it again in the dashboard!** Clicking "Stop Learning" will correctly end the session, save your focus stats to the "7-Day History", and return the dashboard to the standby mode. 

*(Note: Since I restarted the backend, your dashboard might have already auto-refreshed back to the "Start Learning" state. You can safely start a new test session and stop it whenever you want!)*

---

**User**

cd C:\Nanjing_Company_project\supervision_bot 
 python main.py --name 小明 --age 10 
 run this

**Assistant**

I have started the full application process for you!

Here is an explanation of what I did and what was happening:

### What I Fixed:
1. **The Language and Output Error**: When you tried to run `python main.py --name 小明 --age 10` manually, it crashed. This happened because the Windows terminal uses an encoding (`cp1252`) that cannot print Chinese characters (like "小明") by default. I fixed this by passing `$env:PYTHONIOENCODING="utf-8"` before the command, which forces Python to print everything in UTF-8.
2. **The MediaPipe Crash**: The command you tried to run launches the *full* pipeline (including the camera and AI vision models). However, the `mediapipe` library on your system is missing some internal files (`solutions`), causing it to crash immediately when it tried to initialize face tracking. 
3. **Graceful Fallback**: Since fixing `mediapipe` often requires downgrading Python (which is risky for your setup), I modified the code (`vision/mediapipe_module.py`) to safely handle this error. It now catches the error, prints a warning (`[Warning] MediaPipe solutions module not found`), and disables the camera-based tracking while still allowing the rest of the application (the timers, dashboard, and API) to run perfectly.

### Why "Stop Learning" wasn't working:
In your previous message, you mentioned "Stop Learning" didn't work. As I explained in the previous turn, the "Stop Learning" button on the dashboard was sending the command to the backend, but the backend was only turning off the camera and *forgetting to stop the Pomodoro timer*. Because the timer kept running, the dashboard thought the session was still active. I fixed this in the `logic/session_manager.py` file by making sure `end_session()` also explicitly stops the timer.

### Current Status:
The backend is now successfully running in the background with the command you requested (`python main.py --name 小明 --age 10`). 
You can go to the dashboard (`http://127.0.0.1:8000/dashboard`), switch the language to English, and test the start/stop functionality!

---

**User**

cd C:\Nanjing_Company_project\supervision_bot 
 .\venv\Scripts\python.exe main.py --name 小明 --age 10 run it

**Assistant**

I have restarted the application for you using the command `.\venv\Scripts\python.exe main.py --name 小明 --age 10`.

The backend is now successfully running in the background. It has loaded the `MediaPipe` vision models, initialized the API server at `http://127.0.0.1:8000`, and connected to the database.

You can access the dashboard at `http://127.0.0.1:8000/dashboard`.

---

**User**

on which bases it will determine nim focussed kindly erxplain only

**Assistant**

The AI Homework Supervisor determines whether a child is focused based on a combination of several computer vision metrics, which are evaluated continuously during the "FOCUS" phase of the Pomodoro timer. 

Here are the specific rules and thresholds it uses to determine if a child is focused or distracted:

### 1. Head Gaze & Distraction (`_check_distraction`)
- **How it works**: It uses MediaPipe to track the 3D rotation of the child's head (Yaw, Pitch, Roll).
- **Threshold**: If the child's head turns left or right by more than **35 degrees** (`YAW_DISTRACTED_DEG`), they are considered to be looking away from their desk.
- **Trigger**: If this distracted gaze is sustained continuously for **30 seconds** (`GAZE_DISTRACTED_SEC`), the system flags them as distracted and triggers a "distracted gaze" alert.

### 2. Writing Activity / Optical Flow (`_check_writing_idle`)
- **How it works**: It uses OpenCV Optical Flow to detect movement in the bottom half of the camera frame (where the hands and pen usually are).
- **Threshold**: If the movement score drops below **8.0** (`FLOW_IDLE_THRESHOLD`), it assumes the pen is idle.
- **Trigger**: If the pen remains idle for **60 seconds** (`FLOW_IDLE_SECONDS`), the system triggers a "stopped writing" alert.

### 3. Phone Detection (`_check_phone`)
- **How it works**: It uses the YOLO object detection model to look for cell phones in the frame.
- **Trigger**: If a phone is detected with high confidence for just **5 seconds** (`PHONE_ALERT_SECONDS`), it immediately triggers a high-priority distraction alert.

### 4. Out of Seat (`_check_out_of_seat`)
- **How it works**: It checks if a face or body (shoulders) is visible in the frame.
- **Trigger**: If neither a face nor a body is detected for **60 seconds** (`OUT_OF_SEAT_SECONDS`), it assumes the child has left their desk during study time.

### 5. Fatigue / Sleepiness (`_check_fatigue`)
- **How it works**: It calculates the Eye Aspect Ratio (EAR) by measuring the distance between the eyelids.
- **Threshold**: If the EAR drops below **0.20** (`EAR_CLOSED_THRESHOLD`), the eyes are considered closed.
- **Trigger**: If the eyes remain closed for **10 seconds** (`EAR_FATIGUE_SECONDS`), it triggers a fatigue/drowsiness alert.

### How it Calculates the "Focus Score"
At the end of a session, or continuously on the dashboard, the system calculates a score starting at **100**.
- It deducts **20 points** if the child is currently distracted (looking away).
- It deducts **40 points** if a phone is detected.

### How it rewards "Good Focus" (`_check_good_focus`)
If the child remains in their seat, is not looking away (head yaw is normal), and no phone is detected for **5 continuous minutes**, the system triggers a positive "Good Focus" event to offer encouragement.

---

**User**

i want to know the each and eevrything about this project how we execuyte this what modelw e are usign which techniwues so i csan explain to my team so dont fogrget to sdhsre eaxch inform,ation each part of the project how its executing

**Assistant**

Here is a complete breakdown of the AI Homework Supervision Bot project. I will explain the architecture, the specific AI models and techniques used, how the backend pipeline executes, and how the frontend connects to it.

---

### 1. High-Level Architecture
This project is built using a modern **Python Async Backend (FastAPI)** and a **React/Vite Frontend**. It operates like a classic IoT/Edge device application where heavy Computer Vision (CV) processing happens locally.

- **`vision/`**: Contains the Computer Vision pipeline (MediaPipe, YOLO, OpenCV Optical Flow).
- **`logic/`**: The brain of the app. It houses a State Machine (Pomodoro timer) and a Rules Engine that decides when to trigger alerts based on CV inputs.
- **`data/`**: An asynchronous SQLite database (`aiosqlite`) to log session history and event timestamps.
- **`output/`**: Handles Text-to-Speech (TTS) to give verbal warnings or encouragement to the child.
- **`api/`**: A FastAPI server that provides REST endpoints and a Server-Sent Events (SSE) stream for real-time dashboard updates.
- **`dashboard/`**: The frontend UI built with HTML/JS (or React in the source) that consumes the API.

---

### 2. The AI Models & Vision Techniques
The project uses three distinct computer vision techniques, chosen specifically to run efficiently on a standard CPU/Laptop webcam at 15 FPS (as defined in [config.py](file:///c:/Nanjing_Company_project/supervision_bot/config.py)):

#### A. Google MediaPipe (Face Mesh & Pose)
- **File**: [vision/mediapipe_module.py](file:///c:/Nanjing_Company_project/supervision_bot/vision/mediapipe_module.py)
- **Usage**:
  - **Head Pose (Distraction)**: It uses the 3D Face Mesh to map 6 key facial landmarks (nose, chin, eyes, mouth). It uses OpenCV's `solvePnP` algorithm to calculate the head's Yaw (left/right) and Pitch (up/down). If Yaw > 35°, the child is looking away.
  - **Fatigue (Drowsiness)**: It calculates the **EAR (Eye Aspect Ratio)** by measuring the distance between landmarks on the eyelids. If EAR drops below 0.20 for 10 seconds, it flags fatigue.
  - **Gaze Tracking**: It compares the position of the iris landmarks relative to the eye corners to see where the eyes are pointing.
  - **Posture**: It uses the Pose model to locate the shoulders. If the shoulders are too low in the frame or the distance between the ears and shoulders shrinks, it calculates a "Slouch Score".

#### B. YOLOv8 (Object Detection)
- **File**: [vision/yolo_module.py](file:///c:/Nanjing_Company_project/supervision_bot/vision/yolo_module.py)
- **Usage**:
  - YOLO (You Only Look Once) is a lightweight object detection model.
  - It scans the frame specifically for the classes `"cell phone"`, `"person"`, and `"book"`.
  - To save CPU power, YOLO does not run on every frame. It only runs every 3rd frame (about 5 times a second).

#### C. Dense Optical Flow (Activity Tracking)
- **File**: [vision/optical_flow.py](file:///c:/Nanjing_Company_project/supervision_bot/vision/optical_flow.py)
- **Usage**:
  - Instead of trying to detect a tiny pen using an AI model, the system uses OpenCV's `calcOpticalFlowFarneback`.
  - It creates a Region of Interest (ROI) in the bottom 45% of the screen (the desk area).
  - It measures pixel movement between frames. It subtracts global motion (like the camera shaking or the whole body moving) to isolate localized motion (the hand writing).
  - If the motion score drops below 8.0 for 60 seconds, it triggers a "Stopped Writing" alert.

---

### 3. How the Pipeline Executes (The Main Loop)
The core execution happens inside [logic/session_manager.py](file:///c:/Nanjing_Company_project/supervision_bot/logic/session_manager.py) via `asyncio`.

1. **Initialization**: When `python main.py` is run, it starts the FastAPI server in the background and starts the `SessionManager`'s `run()` loop in the foreground.
2. **Frame Capture**: In a `while self._running:` loop, it grabs a frame from the webcam.
3. **Feature Aggregation**: It passes the frame to MediaPipe, YOLO, and Optical Flow simultaneously. It takes all the results (head yaw, EAR, phone presence, writing score) and bundles them into a single `FeatureVector` object.
4. **The Logic Tick**: Every 1 second, it triggers `_tick_logic()`:
   - It updates the **Pomodoro State Machine** (e.g., moves from FOCUS to BREAK if 25 minutes have passed).
   - It passes the `FeatureVector` to the **Rules Engine** ([logic/rules_engine.py](file:///c:/Nanjing_Company_project/supervision_bot/logic/rules_engine.py)).
   - The Rules Engine checks all thresholds. For example: *Has `phone_detected` been True for 5 continuous seconds?* If yes, it generates an `Event`.
5. **Event Handling**: If an event is generated (e.g., `PHONE_DETECTED`), the system fetches a script from the `ScriptBank`, puts it into the TTS queue, and logs the event to the SQLite database.

---

### 4. Output and Feedback (TTS)
- **File**: [output/tts.py](file:///c:/Nanjing_Company_project/supervision_bot/output/tts.py)
- When an event occurs, the system speaks to the child.
- It uses **edge-tts** (Microsoft Edge's cloud TTS) for high-quality, natural-sounding neural voices. 
- Because cloud TTS causes a delay, the system pre-caches all possible voice lines as `.mp3` files in the `data/tts_cache` folder when the session starts.
- It uses the `pygame` library to play the MP3 audio asynchronously so it doesn't freeze the camera feed.

---

### 5. Frontend & API Communication
- The frontend dashboard does not talk to the camera directly.
- The FastAPI server provides a Server-Sent Events (SSE) endpoint at `/stream/features`.
- The dashboard subscribes to this stream. Once a second, the backend converts the current `FeatureVector` into JSON and pushes it to the browser.
- The browser uses this JSON to update the live "Focus Curve" chart, update the "Face/Phone/Write" status indicators, and flash red if a phone is detected.

---

