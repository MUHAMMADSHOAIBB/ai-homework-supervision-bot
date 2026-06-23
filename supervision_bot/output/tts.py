import asyncio
import hashlib
import os
from pathlib import Path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config

try:
    import pygame
    pygame.mixer.init()
    _PYGAME_OK = True
except Exception:
    _PYGAME_OK = False

try:
    import pyttsx3
    _PYTTSX3_ENGINE = pyttsx3.init()
except Exception:
    _PYTTSX3_ENGINE = None


class TTSEngine:
    """
    Primary: edge-tts (requires internet). Async.
    Fallback: pyttsx3 (offline, synchronous).
    Cache: pre-generated MP3s for all template scripts stored in TTS_CACHE_DIR.
    """

    def __init__(self):
        self.cache_dir = Path(config.TTS_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.latest_path: Path | None = None

    async def speak(self, text: str) -> None:
        if not text:
            return
        # Skip if audio is still playing
        if _PYGAME_OK and pygame.mixer.music.get_busy():
            return
        cached = self.cache_dir / f"{self._cache_key(text)}.mp3"
        if cached.exists():
            await self._play_mp3(cached)
            return
        # Try edge-tts
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE)
            await communicate.save(str(cached))
            await self._play_mp3(cached)
            return
        except Exception as e:
            pass
        # Fallback: pyttsx3
        if config.USE_FALLBACK_TTS and _PYTTSX3_ENGINE:
            try:
                _PYTTSX3_ENGINE.say(text)
                _PYTTSX3_ENGINE.runAndWait()
            except Exception:
                pass

    async def pre_cache_all(self, script_bank) -> None:
        """Pre-generate MP3 for every script in script_bank. Runs as background task."""
        import edge_tts
        for key, templates in script_bank.all_scripts().items():
            for template in templates:
                try:
                    text = template.format(
                        name=script_bank._child_name,
                        minutes=5, break_min=5, focus_min=25, rounds=4
                    )
                    cached = self.cache_dir / f"{self._cache_key(text)}.mp3"
                    if not cached.exists():
                        communicate = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE)
                        await communicate.save(str(cached))
                except Exception:
                    pass

    def is_speaking(self) -> bool:
        """Returns True while audio is currently playing."""
        if _PYGAME_OK:
            try:
                return bool(pygame.mixer.music.get_busy())
            except Exception:
                pass
        return False

    def stop(self) -> None:
        if _PYGAME_OK:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

    def _cache_key(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    async def _play_mp3(self, path: Path) -> None:
        if not _PYGAME_OK:
            return
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            self.latest_path = path
        except Exception:
            pass
