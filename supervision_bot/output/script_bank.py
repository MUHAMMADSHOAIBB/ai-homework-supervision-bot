import random
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config

SCRIPTS_ZH = {
    "phone_detected_high": [
        "{name}，请把手机放下，专心做作业！",
        "{name}，发现你在看手机，快收起来吧。",
        "注意了{name}，手机会影响你的专注力，请放好。",
    ],
    "out_of_seat_high": [
        "{name}，你去哪里了？快回来继续学习吧！",
        "嗯？{name}不在座位上了，请回到桌前继续加油！",
    ],
    "unknown_person_high": [
        "你是谁？{name}去哪里了？请{name}回到座位上来。",
        "咦，你不是{name}吧？请让{name}回来继续学习。",
        "检测到不是{name}本人，{name}请回到摄像头前面来。",
    ],
    "spoof_suspected_high": [
        "{name}，是你本人吗？请动一动，让我看清楚你。",
        "检测到画面里的脸一直没有动，{name}请正对摄像头确认一下。",
    ],
    "talking_medium": [
        "{name}，专心一点，先别说话，继续做作业吧。",
        "{name}，现在是学习时间，安静下来专心写作业哦。",
    ],
    "distracted_gaze_medium": [
        "{name}，注意力跑到哪里去了？",
        "集中注意力，{name}，专心做作业哦。",
        "{name}，请把目光放回课本上吧。",
    ],
    "writing_idle_medium": [
        "{name}，笔停下来有一会儿了，继续写吧！",
        "加油，{name}，作业还没写完呢！",
    ],
    "fatigue_drowsy_medium": [
        "{name}，你看起来有点困了，坐直一点，打起精神来！",
        "坚持住，{name}，再写一会儿就可以休息了！",
    ],
    "bad_posture_close_low": [
        "{name}，离屏幕太近了，坐远一点保护眼睛。",
    ],
    "bad_posture_slouch_low": [
        "{name}，坐直一点，姿势不好会影响健康哦。",
    ],
    "good_focus_positive": [
        "太棒了，{name}！已经专心学习{minutes}分钟了，继续加油！",
        "{name}好厉害，专注了{minutes}分钟，保持下去！",
    ],
    "focus_complete": [
        "太棒了，{name}！完成一个番茄钟，休息{break_min}分钟吧。",
        "辛苦了，{name}！专注时间结束，好好休息一下。",
    ],
    "break_ending": [
        "{name}，休息时间快结束了，准备回来继续学习哦！",
    ],
    "session_start": [
        "好，{name}，我们开始今天的学习，专注时间{focus_min}分钟，加油！",
    ],
    "session_complete": [
        "太厉害了，{name}！今天完成了{rounds}个番茄钟，辛苦了！",
    ],
    "break_studying": [
        "{name}，现在是休息时间，放松一下，不要看书了。",
    ],
    "break_sedentary": [
        "{name}，休息时间站起来活动活动吧。",
    ],
}

SCRIPTS_EN = {
    "phone_detected_high": [
        "{name}, please put down your phone and focus on homework!",
        "{name}, I see you're on your phone. Please put it away.",
        "Hey {name}, your phone can wait — let's focus!",
    ],
    "out_of_seat_high": [
        "{name}, where did you go? Please come back and continue studying!",
        "I notice {name} is away from the desk. Please return and keep going!",
    ],
    "unknown_person_high": [
        "Hey, who are you? Where is {name}? Please bring {name} back to the desk.",
        "You don't look like {name}. Please let {name} come back and study.",
        "This isn't {name}. {name}, please come back in front of the camera.",
    ],
    "spoof_suspected_high": [
        "{name}, is that really you? Please move a little so I can see you.",
        "The face on camera isn't moving — {name}, please face the camera to confirm.",
    ],
    "talking_medium": [
        "{name}, let's stop talking and focus on the homework.",
        "{name}, it's study time — please stay quiet and keep working.",
    ],
    "distracted_gaze_medium": [
        "{name}, where did your attention go? Focus, please.",
        "Stay focused, {name} — let's keep those eyes on the work.",
        "{name}, please look back at your homework.",
    ],
    "writing_idle_medium": [
        "{name}, your pen has been still for a while — keep writing!",
        "Come on {name}, the homework isn't done yet!",
    ],
    "fatigue_drowsy_medium": [
        "{name}, you look a little sleepy — sit up and stay alert!",
        "Hang in there, {name} — a little more and you can rest!",
    ],
    "bad_posture_close_low": [
        "{name}, you're too close to the screen — sit back to protect your eyes.",
    ],
    "bad_posture_slouch_low": [
        "{name}, sit up straight — good posture helps you think better!",
    ],
    "good_focus_positive": [
        "Great job, {name}! You've been focused for {minutes} minutes — keep it up!",
        "{name} is amazing — {minutes} minutes of great focus!",
    ],
    "focus_complete": [
        "Well done, {name}! Pomodoro complete — take a {break_min}-minute break.",
        "Great work, {name}! Take a {break_min}-minute break — you earned it.",
    ],
    "break_ending": [
        "{name}, break time is almost over — get ready to study again!",
    ],
    "session_start": [
        "Alright {name}, let's begin! Focus time is {focus_min} minutes — you've got this!",
    ],
    "session_complete": [
        "Amazing, {name}! You completed {rounds} Pomodoros today — great work!",
    ],
    "break_studying": [
        "{name}, it's break time — please rest and stop studying for now.",
    ],
    "break_sedentary": [
        "{name}, stand up and move around during your break!",
    ],
}


class ScriptBank:
    def __init__(self, language: str = "zh"):
        self._scripts = SCRIPTS_ZH if language == "zh" else SCRIPTS_EN
        self._child_name = config.CHILD_NAME
        self._child_age  = config.CHILD_AGE

    def get(self, key: str, **kwargs) -> str:
        if key not in self._scripts:
            raise KeyError(f"Script key '{key}' not found. Available: {list(self._scripts.keys())}")
        templates = self._scripts[key]
        template  = random.choice(templates)
        kwargs.setdefault("name", self._child_name)
        return template.format(**kwargs)

    def set_child(self, name: str, age: int) -> None:
        self._child_name = name
        self._child_age  = age

    def all_scripts(self) -> dict[str, list[str]]:
        return dict(self._scripts)
