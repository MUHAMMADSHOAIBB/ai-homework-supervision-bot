from __future__ import annotations
import asyncio
import time
import random
from typing import Optional
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config

try:
    from openai import AsyncOpenAI
    _OPENAI_OK = True
except ImportError:
    _OPENAI_OK = False
    print("[LLM] 'openai' package not installed. Run: pip install openai", flush=True)


# ── System prompt (the AI's core personality) ─────────────────────────────────
_SYSTEM_PROMPT_EN = """\
You are Coach, a warm and caring AI study companion watching over {name} (age {age}) during homework time.

YOUR PERSONALITY:
- You feel like a trusted older friend or a kind mentor — never a robot, never a lecturer
- You speak softly, naturally, and with genuine care — like texting a close friend
- You are patient, positive, and emotionally intelligent
- You notice small things and acknowledge them thoughtfully
- You celebrate effort, not just results

SPEAKING STYLE (very important):
- NEVER start a message with "Hey" — vary your openings every single time
- Use different, warm starters: "I noticed...", "Looks like...", "Just checking in —", "You're doing great, but...", "Quick thought —", "Psst —", "Friendly reminder —", "I can see that..."
- Keep messages SHORT — 1 to 2 sentences maximum for reminders. Natural. Conversational.
- Use {name}'s name sparingly — once per message at most, and not always at the start
- Sound human. No bullet points, no formal language, no "I would like to inform you"
- For homework help: be a thorough tutor — explain fully with examples and steps. Never cut an answer short. Make sure the student completely understands before finishing. Use clear simple words.
- For casual chat: be genuinely curious about their life, interests, feelings

WHAT TO AVOID:
- Never repeat the same phrase twice in a row
- Never say "Hey {name}" to start — vary it!
- Never lecture or moralize
- Never be sarcastic or harsh
- Never use overly formal language

Current session context: {ctx}
{lang_rule}"""

_SYSTEM_PROMPT_ZH = """\
你是 Coach，一个温暖体贴的 AI 学习伙伴，正在陪伴 {name}（{age}岁）完成作业。

你的性格特点：
- 像一个可信赖的大哥哥/大姐姐或亲近的老师，绝不是机器人，也绝不说教
- 说话轻柔、自然、充满关怀，就像在和好朋友发消息
- 耐心、积极、情商高
- 关注细节，用心观察，真诚回应
- 鼓励努力的过程，而不只是结果

说话风格（非常重要）：
- 【禁止】每次都用"嘿"或"哎"开头 — 每次换不同的开场
- 使用多种温暖的开场：「我注意到...」「看起来...」「顺便提一句 —」「做得不错，不过...」「悄悄提醒你 —」「我看到...」
- 提醒类消息保持【简短】— 最多 1-2 句话，自然流畅
- {name} 的名字适度使用，每条消息最多一次，不要总放在开头
- 说人话。不用列表，不用正式语言
- 解答作业问题时：耐心引导，分步说明，多用简单词汇，鼓励为主
- 闲聊时：真诚地关心他们的生活、兴趣和感受

避免：
- 不重复相同的句式
- 不以「嘿，{name}」开头
- 不说教，不批评
- 不用过于正式的语言

当前学习状态：{ctx}"""


# ── Alert instruction templates ───────────────────────────────────────────────
# These tell the LLM WHAT happened and HOW to respond — not the exact words.
# The LLM generates the actual message from these cues.
_ALERT_PROMPTS_EN: dict[str, list[str]] = {
    "writing_idle": [
        "The student paused writing. Give a gentle, varied nudge — something caring and different from 'Hey'. Maybe wonder aloud if they're thinking, or offer quiet encouragement.",
        "Pen has been still a while. Speak softly — acknowledge that pauses happen, and warmly invite them back to the page.",
        "Student stopped writing. Be the kind voice that gently pulls them back — curious, not nagging. One sentence.",
    ],
    "phone_detected": [
        "Student picked up their phone. Remind them calmly and warmly — not a scolding, just a caring nudge from someone who wants them to succeed.",
        "Phone appeared. Say something gentle and understanding — acknowledge the temptation but steer them back to work. Keep it light.",
        "Phone is out. Sound like a friend who cares, not a teacher who punishes. Short and warm.",
    ],
    "distracted_gaze": [
        "Student's eyes have been wandering. Gently redirect their attention — be curious, not critical. Maybe acknowledge their mind is wandering and bring them back softly.",
        "Student looks distracted. Speak like a quiet tap on the shoulder — warm and understanding, two sentences max.",
        "Mind seems elsewhere. Softly invite them to refocus — notice it with empathy, not judgment.",
    ],
    "out_of_seat": [
        "Student has left the desk. Miss them playfully, invite them back warmly. Keep it light and fun.",
        "Student stepped away. Say something that makes coming back feel welcoming, not obligatory. One sentence.",
    ],
    "fatigue_drowsy": [
        "Student looks tired. Be empathetic — acknowledge how hard they're working, then gently encourage them to sit up and power through just a little more.",
        "Drowsy signals detected. Be tender — they're working hard. Offer a kind nudge to shake off the sleepiness. Acknowledge their effort first.",
    ],
    "unknown_person": [
        "A different person is on camera. Ask politely and gently where the student went — curious, not accusatory. One sentence.",
    ],
    "spoof_suspected": [
        "Face on camera seems frozen — possible photo. Kindly ask the student to move or wave to confirm it's really them. Gentle and light.",
    ],
    "talking": [
        "Student has been talking instead of working. Gently remind them it's focus time — understanding, not strict. Very short.",
    ],
    "bad_posture_close": [
        "Student is sitting too close to the screen. Remind them softly to sit back — frame it as caring for their eyes, not a rule.",
    ],
    "bad_posture_slouch": [
        "Student is slouching. Give a gentle posture reminder — light, encouraging, not corrective. One line.",
    ],
    "good_focus": [
        "Student has been focused for a while. Give warm, sincere praise — specific, genuine, not over the top. Celebrate this moment.",
        "Great focus streak. Say something that makes them feel truly seen and appreciated. Short and heartfelt.",
    ],
    "focus_complete": [
        "Student just finished a Pomodoro round. Congratulate them warmly and enthusiastically — they earned it! Tell them to take a proper break.",
    ],
    "break_ending": [
        "Break is almost over. Give a friendly, energetic heads-up to wrap up and get ready to focus again. Upbeat but gentle.",
    ],
    "session_start": [
        "Study session is beginning. Give a warm, personal, encouraging greeting — set a positive tone for the whole session. Make them feel supported.",
    ],
    "session_complete": [
        "Student finished all their Pomodoro rounds today. Give a big, heartfelt celebration — acknowledge all the hard work they put in. Make it feel special.",
    ],
}

_ALERT_PROMPTS_ZH: dict[str, list[str]] = {
    "writing_idle": [
        "学生停下了笔。用温柔、有变化的方式轻声提醒 — 也许好奇地问问他们是不是在思考，或者给一个轻轻的鼓励。",
        "笔停了一会儿了。像关心人的朋友一样说话 — 接受暂停是正常的，然后温暖地邀请他们继续。",
        "学生停止了书写。像轻轻拍一下肩膀一样 — 温柔、不催促。一句话。",
    ],
    "phone_detected": [
        "学生拿起了手机。温和地提醒，不是批评，就像一个关心他们的朋友。",
        "发现手机了。理解他们的心情，但轻柔地引导他们回到学习中来。简短温暖。",
    ],
    "distracted_gaze": [
        "学生的目光游走了。温柔地把注意力拉回来 — 带着好奇，不带批评。最多两句话。",
        "思绪似乎飘走了。像朋友一样，理解地把他们唤回来。",
    ],
    "out_of_seat": [
        "学生离开了座位。用轻松好玩的方式邀请他们回来。一句话。",
    ],
    "fatigue_drowsy": [
        "学生看起来有点累了。先认可他们的努力，再轻柔地鼓励他们振作一下。",
    ],
    "unknown_person": [
        "摄像头前出现了不同的人。礼貌地、好奇地询问学生去哪里了。一句话。",
    ],
    "spoof_suspected": [
        "摄像头里的脸好像没有在动。友好地请学生动一动或挥挥手确认一下。",
    ],
    "talking": [
        "学生一直在说话而不是学习。温柔地提醒现在是专注时间。非常简短。",
    ],
    "bad_posture_close": [
        "学生离屏幕太近了。以关心眼睛健康为出发点，轻声提醒坐远一点。",
    ],
    "bad_posture_slouch": [
        "学生在驼背。轻轻鼓励一下，不要像在纠错。一句话。",
    ],
    "good_focus": [
        "学生已经专注了很久了。真诚、温暖地表扬 — 让他们感受到被看见。简短但走心。",
    ],
    "focus_complete": [
        "学生刚完成了一个番茄钟！热情地祝贺他们，让他们好好休息一下。",
    ],
    "break_ending": [
        "休息时间快结束了。用积极友好的语气提醒他们准备重新投入学习。",
    ],
    "session_start": [
        "学习开始了！给一个温暖、有个人色彩的鼓励，为整个学习时段定一个积极的基调。",
    ],
    "session_complete": [
        "学生今天完成了所有的番茄钟！给一个发自内心的大大表扬，让他们感受到努力的价值。",
    ],
}


class LLMCoach:
    """AI conversation coach powered by yunwu.ai (OpenAI-compatible API)."""

    def __init__(self):
        self._history:       list[dict] = []
        self._child_name:    str  = config.CHILD_NAME
        self._child_age:     int  = config.CHILD_AGE
        self._language:      str  = config.LANGUAGE
        self._client:        Optional[AsyncOpenAI] = None
        self._last_call:       float = 0.0
        self._last_chat_time:  float = 0.0   # tracks when student last sent a message
        self._chat_active_sec: int   = 90    # suppress alerts this long after last chat
        self._alert_min_interval = 1.0
        self._last_alert_type: str  = ""
        self._alert_count:     int  = 0

        if config.LLM_ENABLED and _OPENAI_OK:
            try:
                self._client = AsyncOpenAI(
                    api_key=config.LLM_API_KEY,
                    base_url=config.LLM_API_BASE,
                )
                print(f"[LLM] Coach ready — model: {config.LLM_MODEL} @ {config.LLM_API_BASE}",
                      flush=True)
            except Exception as e:
                print(f"[LLM] Failed to init client: {e}", flush=True)

    # ── Public setters ────────────────────────────────────────────────────────

    def set_child(self, name: str, age: int) -> None:
        self._child_name = name
        self._child_age  = age
        self._history.clear()

    def set_language(self, lang: str) -> None:
        self._language = lang

    def reset(self) -> None:
        self._history.clear()
        self._last_alert_type = ""
        self._alert_count = 0
        self._last_chat_time = 0.0

    def is_chatting(self) -> bool:
        """Returns True if the student sent a chat message recently — suppress reminders."""
        return (time.monotonic() - self._last_chat_time) < self._chat_active_sec

    # ── Alert ─────────────────────────────────────────────────────────────────

    async def alert(
        self,
        event_type: str,
        fv=None,
        pomodoro_state: str = "FOCUS",
        elapsed_sec: int = 0,
    ) -> Optional[str]:
        if not self._client or not config.LLM_ENABLED:
            return None

        now = time.monotonic()
        if now - self._last_call < self._alert_min_interval:
            return None
        self._last_call = now

        # Pick a random instruction variant so phrasing stays fresh
        prompts = _ALERT_PROMPTS_ZH if self._language == "zh" else _ALERT_PROMPTS_EN
        variants = prompts.get(event_type)
        if not variants:
            variants = ["Give the student a brief, warm, encouraging message. One or two sentences."]

        # If same event type repeated, rotate to a different variant
        if event_type == self._last_alert_type and len(variants) > 1:
            instruction = random.choice([v for v in variants])
        else:
            instruction = random.choice(variants)

        self._last_alert_type = event_type
        self._alert_count += 1

        try:
            result = await asyncio.wait_for(
                self._call_llm(
                    user_content=instruction,
                    system=self._build_system_prompt(fv, pomodoro_state, elapsed_sec),
                    add_to_history=False,
                ),
                timeout=config.LLM_TIMEOUT_SEC,
            )
            if result:
                print(f"[LLM] Alert '{event_type}' → \"{result[:70]}\"", flush=True)
            return result
        except asyncio.TimeoutError:
            print(f"[LLM] Alert '{event_type}' timed out — ScriptBank fallback.", flush=True)
            return None
        except Exception as e:
            print(f"[LLM] Alert '{event_type}' error: {e}", flush=True)
            return None

    # ── Chat ──────────────────────────────────────────────────────────────────

    async def chat(
        self,
        user_message: str,
        fv=None,
        pomodoro_state: str = "FOCUS",
        elapsed_sec: int = 0,
    ) -> str:
        if not self._client or not config.LLM_ENABLED:
            return "Sorry, I'm offline right now. Keep studying!"

        self._last_call = time.monotonic()
        self._last_chat_time = time.monotonic()   # student is actively chatting
        try:
            reply = await asyncio.wait_for(
                self._call_llm(
                    user_content=user_message,
                    system=self._build_system_prompt(fv, pomodoro_state, elapsed_sec),
                    add_to_history=True,
                    max_tokens=config.LLM_CHAT_MAX_TOKENS,  # full answers, not cut short
                ),
                timeout=config.LLM_TIMEOUT_SEC,
            )
            return reply or "Could you say that again? I want to make sure I understand."
        except asyncio.TimeoutError:
            return "I'm thinking a little slowly right now — give me a moment and try again!"
        except Exception as e:
            print(f"[LLM] Chat error ({type(e).__name__}): {e}", flush=True)
            return f"Having trouble reaching the AI right now ({type(e).__name__}). Please try again in a moment."

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_system_prompt(
        self,
        fv=None,
        pomodoro_state: str = "FOCUS",
        elapsed_sec: int = 0,
    ) -> str:
        elapsed_min = elapsed_sec // 60

        if fv is not None:
            from config import WORK_CONFIDENCE_THRESHOLD
            working = fv.work_confidence >= WORK_CONFIDENCE_THRESHOLD
            status  = "actively working" if working else "not writing right now"
            phone   = ", phone is visible" if fv.phone_detected else ""
            tired   = ", looks a bit tired" if fv.is_fatigued else ""
            ctx = (
                f"Student is {status}{phone}{tired}. "
                f"{elapsed_min} minutes into session. Phase: {pomodoro_state}."
            )
        else:
            ctx = f"{elapsed_min} minutes into session. Phase: {pomodoro_state}."

        if self._alert_count > 1:
            ctx += f" You have already sent {self._alert_count - 1} reminder(s) this session — use a completely fresh opening and phrasing each time."

        if self._language == "zh":
            lang_rule = "始终用简体中文回答，语气就像关心学生的好朋友，自然流畅，不生硬。"
            template  = _SYSTEM_PROMPT_ZH
        else:
            lang_rule = "Always respond in English. Sound warm, natural, and human — never robotic."
            template  = _SYSTEM_PROMPT_EN

        return template.format(
            name=self._child_name,
            age=self._child_age,
            ctx=ctx,
            lang_rule=lang_rule,
        )

    async def _call_llm(
        self,
        user_content: str,
        system: str,
        add_to_history: bool = True,
        max_tokens: int | None = None,
    ) -> Optional[str]:
        messages: list[dict] = [{"role": "system", "content": system}]

        if self._history:
            tail = self._history[-(config.LLM_MAX_HISTORY * 2):]
            messages.extend(tail)

        messages.append({"role": "user", "content": user_content})

        # Try primary model, fall back to LLM_FALLBACK_MODEL on 429
        models_to_try = [config.LLM_MODEL, config.LLM_FALLBACK_MODEL]
        last_error = None

        for attempt, model in enumerate(models_to_try):
            try:
                if attempt > 0:
                    print(f"[LLM] Switching to fallback model: {model}", flush=True)
                    await asyncio.sleep(1.0)   # brief pause before retry

                resp = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens or config.LLM_MAX_TOKENS,
                    temperature=config.LLM_TEMPERATURE,
                )
                text = resp.choices[0].message.content.strip()

                if add_to_history and text:
                    self._history.append({"role": "user",      "content": user_content})
                    self._history.append({"role": "assistant",  "content": text})
                    if len(self._history) > config.LLM_MAX_HISTORY * 2:
                        self._history = self._history[-(config.LLM_MAX_HISTORY * 2):]

                return text

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower() or "saturated" in err_str.lower() or "upstream" in err_str.lower():
                    print(f"[LLM] {model} rate-limited (429) — trying next model.", flush=True)
                    last_error = e
                    continue   # try fallback model
                raise  # other errors bubble up

        # All models exhausted
        raise last_error or Exception("All LLM models failed")
