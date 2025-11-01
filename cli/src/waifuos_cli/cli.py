import asyncio
import base64
from datetime import datetime
from zoneinfo import ZoneInfo
import io
import logging
import os
from pathlib import Path
import select
import shutil
import sys
try:
    import termios
    import tty
except ImportError:
     # Windows fallback
    termios = None
    tty = None
from typing import Dict, AsyncGenerator, Optional, Union
from uuid import uuid4
from dotenv import set_key
import httpx
try:
    from .audio import AudioDevice, AudioPlayer
except:
    class AudioDeviceDummy:
        def __init__(self, output_device: int = -1):
            self.output_device = output_device
    class AudioPlayerDummy:
        def __init__(self, device_index: int, chunk_size: int = 1024):
            pass
        def add(self, audio_bytes: bytes, has_wave_header: bool = False):
            pass
        def stop(self):
            pass
from PIL import Image
from pydantic import BaseModel

logger = logging.getLogger(__name__)

RESET = "\033[0m"
BOLD = "\033[1m"
ITALIC = "\033[3m"


class AvatarControlRequest(BaseModel):
    animation_name: Optional[str] = None
    animation_duration: Optional[float] = None
    face_name: Optional[str] = None
    face_duration: Optional[float] = None


class AIAvatarResponse(BaseModel):
    type: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    context_id: Optional[str] = None
    text: Optional[str] = None
    voice_text: Optional[str] = None
    language: Optional[str] = None
    avatar_control_request: Optional[AvatarControlRequest] = None
    audio_data: Optional[Union[bytes, str]] = None
    metadata: Optional[Dict] = None


class _NullInterruptWatcher:
    def __enter__(self):
        self.last_key = None
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def should_interrupt(self) -> bool:
        return False


class _InterruptWatcher:
    ESC_KEY = b"\x1b"
    CTRL_C_KEY = b"\x03"
    CANCEL_KEYS = {ESC_KEY, CTRL_C_KEY}

    def __init__(self):
        self.fd = sys.stdin.fileno()
        self._original_attrs = None
        self.last_key = None

    def __enter__(self):
        if termios and tty:
            self._original_attrs = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        self.last_key = None
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._original_attrs and termios:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._original_attrs)
        return False

    def should_interrupt(self) -> bool:
        if self._original_attrs is None or termios is None:
            return False

        ready, _, _ = select.select([self.fd], [], [], 0)
        if not ready:
            return False

        try:
            key = os.read(self.fd, 1)
        except OSError:
            return False

        self.last_key = key

        if key in self.CANCEL_KEYS:
            # Drain any escape sequence tail (e.g. arrow keys).
            while select.select([self.fd], [], [], 0)[0]:
                try:
                    os.read(self.fd, 1)
                except OSError:
                    break
            return True

        return False


class WaifuCLI:
    def __init__(
        self,
        *,
        default_env_path: Path,
        # Waifu server info
        base_url: str = "http://localhost:8012/aiavatar/api",
        api_key: str = None,
        # Session info
        session_id: str = None,
        user_id: str = None,
        on_start_message_prompt: str = None,
        timezone: str = "Asia/Tokyo",
        # Presentation settings
        character_voice_enabled: bool = True,
        faces: Dict[str, str] = None,
        character_interval: float = 0.02,   # Message speed
        icon_width_ratio: float = 0.5,      # Clamp icon width to 50% of terminal columns.
        icon_max_width: int = 40,           # Hard cap in columns; tweak to taste.
        icon_min_width: int = 20,           # Avoid collapsing too small.
        icon_aspect_ratio: float = 1.0,     # 1.0 keeps aspect ratio; lower to flatten slightly.
        use_truecolor: bool = False,
        waifu_label_color: str = "\033[38;2;255;64;160m",  # Deep pink
        user_label_color: str = "\033[38;2;80;200;120m",   # Soft green
        face_color: str = "\033[38;2;255;224;243m",        # Soft blush pink
        # Client configurations
        timeout: float = 60.0,
        audio_devices = None,
        output_device_index: int = -1,
        output_chunk_size: int = 1024,
        debug = False,
    ):
        self.default_env_path = default_env_path
        self.debug = debug

        # Waifu server
        self.base_url = base_url
        self.api_key = api_key

        # HTTP Client
        self.http_client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(connect=10.0, timeout=timeout),
        )

        # Audio player
        self.character_voice_enabled = character_voice_enabled
        if audio_devices:
            self.audio_devices = audio_devices
        else:
            self.audio_devices = AudioDevice(output_device=output_device_index)
        self.audio_player = AudioPlayer(
            device_index=self.audio_devices.output_device,
            chunk_size=output_chunk_size
        )

        # Session data
        self.session_id = session_id or f"waifu_ses_{uuid4()}"
        self.user_id = user_id
        self.context_id: str = None
        self.waifu_image_bytes: bytes = None
        self.waifu_name: str = None
        self.user_name: str = None
        self.relation: str = None
        self.on_start_message_prompt = on_start_message_prompt
        self.timezone = timezone

        # Presentation
        self.faces = faces or {
            "neutral": "('_')",
            "joy": "(^o^)",
            "angry": "(#｀Д´)",
            "sorrow": "(; ;)",
            "fun": "(*^_^*)",
        }
        self.character_interval = character_interval
        self.icon_width_ratio = icon_width_ratio
        self.icon_max_width = icon_max_width
        self.icon_min_width = icon_min_width
        self.icon_aspect_ratio = icon_aspect_ratio
        self.use_truecolor = use_truecolor
        self.waifu_label_color = self.to_safe_color(waifu_label_color)
        self.user_label_color = self.to_safe_color(user_label_color)
        self.face_color = self.to_safe_color(face_color)
        self.processing_color = self.to_safe_color("\033[38;2;102;102;102m")
        self.interrupted_color = self.to_safe_color("\033[90m")

        # Interrupt and exit
        self.interrupted_message = "Response interrupted"
        self.exit_commands = ["exit", "bye"]
        self.goodbye_char = "👋\n"
        self.goodbye_printed = False

    def print_goodbye(self, prefix_newline: bool = False):
        if self.goodbye_printed:
            return
        if prefix_newline:
            sys.stdout.write("\n")
        sys.stdout.write(self.goodbye_char)
        sys.stdout.flush()
        self.goodbye_printed = True

    def rgb_to_ansi256(self, red: int, green: int, blue: int) -> int:
        cube_levels = [0, 95, 135, 175, 215, 255]
        r_idx = max(0, min(5, int(round(red / 255 * 5))))
        g_idx = max(0, min(5, int(round(green / 255 * 5))))
        b_idx = max(0, min(5, int(round(blue / 255 * 5))))

        cube_r = cube_levels[r_idx]
        cube_g = cube_levels[g_idx]
        cube_b = cube_levels[b_idx]
        cube_distance = (
            (cube_r - red) ** 2 +
            (cube_g - green) ** 2 +
            (cube_b - blue) ** 2
        )
        cube_index = 16 + (36 * r_idx) + (6 * g_idx) + b_idx

        grayscale_levels = [8 + i * 10 for i in range(24)]
        grayscale_index = 232
        grayscale_distance = float("inf")
        for offset, level in enumerate(grayscale_levels):
            distance = (
                (level - red) ** 2 +
                (level - green) ** 2 +
                (level - blue) ** 2
            )
            if distance < grayscale_distance:
                grayscale_distance = distance
                grayscale_index = 232 + offset

        if grayscale_distance < cube_distance:
            return grayscale_index
        return cube_index

    def to_safe_color(self, color: str) -> str:
        if self.use_truecolor:
            return color
        if not color.startswith("\033[") or not color.endswith("m"):
            return color

        body = color[2:-1]
        segments = body.split(";")
        converted = False
        result_segments = []

        try:
            i = 0
            while i < len(segments):
                seg = segments[i]
                if seg in ("38", "48") and i + 4 < len(segments) and segments[i + 1] == "2":
                    red = int(segments[i + 2])
                    green = int(segments[i + 3])
                    blue = int(segments[i + 4])
                    ansi_index = self.rgb_to_ansi256(red, green, blue)
                    result_segments.extend([seg, "5", str(ansi_index)])
                    converted = True
                    i += 5
                else:
                    result_segments.append(seg)
                    i += 1
        except ValueError:
            return color

        if not converted:
            return color

        return f"\033[{';'.join(result_segments)}m"

    def render_start_banner(self, image_bytes: bytes):
        term_cols, _ = shutil.get_terminal_size(fallback=(80, 24))
        term_cols = max(10, term_cols)

        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("RGB")
            aspect_ratio = img.height / img.width if img.width else 1

            desired_width = term_cols
            if self.icon_width_ratio:
                desired_width = min(desired_width, max(1, int(term_cols * self.icon_width_ratio)))
            if self.icon_max_width:
                desired_width = min(desired_width, self.icon_max_width)

            desired_width = max(self.icon_min_width, desired_width)
            target_width = min(desired_width, img.width)
            target_height = max(2, int(target_width * aspect_ratio * self.icon_aspect_ratio))

            resample_base = getattr(Image, "Resampling", Image)
            img = img.resize((target_width, target_height), resample=resample_base.LANCZOS)
            pixels = img.load()

            for y in range(0, target_height, 2):
                line_parts = []
                for x in range(target_width):
                    top_r, top_g, top_b = pixels[x, y]
                    if y + 1 < target_height:
                        bottom_r, bottom_g, bottom_b = pixels[x, y + 1]
                        if self.use_truecolor:
                            fg_seq = f"\033[38;2;{top_r};{top_g};{top_b}m"
                            bg_seq = f"\033[48;2;{bottom_r};{bottom_g};{bottom_b}m"
                        else:
                            fg_seq = f"\033[38;5;{self.rgb_to_ansi256(top_r, top_g, top_b)}m"
                            bg_seq = f"\033[48;5;{self.rgb_to_ansi256(bottom_r, bottom_g, bottom_b)}m"
                        line_parts.append(f"{fg_seq}{bg_seq}▀")
                    else:
                        # No lower pixel: reset background so it stays transparent.
                        if self.use_truecolor:
                            fg_seq = f"\033[38;2;{top_r};{top_g};{top_b}m"
                        else:
                            fg_seq = f"\033[38;5;{self.rgb_to_ansi256(top_r, top_g, top_b)}m"
                        line_parts.append(f"{fg_seq}\033[49m▀")
                sys.stdout.write("".join(line_parts) + RESET + "\n")

        sys.stdout.write(RESET + "\n")
        sys.stdout.flush()

    def interrupt_watcher(self):
        if termios and tty:
            return _InterruptWatcher()
        return _NullInterruptWatcher()

    async def init_chat(self, user_id: str):
        # Get waifu
        waifu_resp = await self.http_client.get(
            url=self.base_url + f"/waifu",
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else None
        )
        waifu_resp.raise_for_status()
        waifu_info = waifu_resp.json()
        if waifu_info.get("error"):
            raise Exception(waifu_info["error"])
        self.waifu_id = waifu_info.get("waifu_id")
        self.waifu_name = waifu_info.get("waifu_name")
        self.waifu_image_bytes = base64.b64decode(waifu_info.get("waifu_image"))

        # Get or create user
        user_params = {"waifu_id": self.waifu_id}
        if self.user_id:
            user_params["user_id"] = self.user_id
        user_resp = await self.http_client.get(
            url=self.base_url + f"/user",
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else None,
            params=user_params
        )
        user_resp.raise_for_status()
        user_info = user_resp.json()
        if user_info.get("error"):
            raise Exception(user_info["error"])

        # Save the user_id when it’s missing from .env or differs from the current user_id in .env (for example, when .env contains a non-existent UID).
        if not self.user_id or self.user_id != user_info["user_id"]:
            self.user_id = user_info["user_id"]
            set_key(str(self.default_env_path), "USER_ID", self.user_id)
            os.environ["USER_ID"] = self.user_id
        self.user_name = user_info["user_name"]
        self.relation = user_info["relation"]

        # Get context
        context_resp = await self.http_client.get(
            url=self.base_url + "/context",
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else None,
            params={"user_id": self.user_id}
        )
        context_resp.raise_for_status()
        context_info = context_resp.json()
        if context_info.get("error"):
            raise Exception(context_info["error"])
        self.context_id = context_info.get("context_id")

    async def play_voice(self, voice_text: str, language: str = None):
        payload = {"text": voice_text}
        if language:
            payload["language"] = language
        voice_resp = await self.http_client.post(
            url=self.base_url + "/synthesize",
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else None,
            json=payload
        )
        self.audio_player.add(await voice_resp.aread(), True)

    async def send_request(self, text: str) -> AsyncGenerator[str, None]:
        async with self.http_client.stream(
            method="post",
            url=self.base_url + "/chat",
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else None,
            json={
                "type": "start",
                "session_id": self.session_id,
                "user_id": self.user_id,
                "context_id": self.context_id,
                "text": text
            }
        ) as response:
            if response.status_code != 200:
                logger.error(f"HTTP error {response.status_code}: {await response.aread()}")
                response.raise_for_status()

            async for chunk in response.aiter_lines():
                yield ""    # yield empty to enable ESC interruption

                if chunk.startswith("data:"):
                    response = AIAvatarResponse.model_validate_json(chunk[5:].strip())

                    if response.context_id:
                        self.context_id = response.context_id

                    if response.type == "chunk":
                        # Face
                        if face_name := response.avatar_control_request.face_name:
                            if face_expression := self.faces.get(face_name.lower()):
                                yield f"{BOLD}{self.face_color}{face_expression}{RESET} "

                        # Text
                        if response.voice_text:
                            yield response.voice_text
                            if self.character_voice_enabled:
                                await self.play_voice(response.voice_text)

                    elif response.type == "tool_call":
                        tool_name = ""
                        try:
                            tool_name = response.metadata["tool_call"]["name"]
                            if response.metadata["tool_call"]["result"]["data"]:
                                yield f"{BOLD}{ITALIC}{self.processing_color}[Finish {tool_name} !]{RESET}\n"
                                # Update user name
                                if tool_name == "update_userinfo":
                                    if user_name := response.metadata["tool_call"]["result"]["data"].get("username"):
                                        self.user_name = user_name
                                    if relation := response.metadata["tool_call"]["result"]["data"].get("relation"):
                                        self.relation = relation
                            else:
                                yield f"{BOLD}{ITALIC}{self.processing_color}[Processing {tool_name} ...]{RESET}\n"
                        except:
                            pass

                    elif response.type == "error":
                        logger.error(f"Error in processing response: {response.model_dump()}")

    async def start(self):
        try:
            await self.init_chat(self.user_id)
        except httpx.HTTPStatusError as htserr:
            if htserr.response.status_code == 404:
                print(f"💔 No waifus on your server yet. 'waifu create' before start chatting. ({self.base_url}): {htserr}")
            else:
                print(f"💔 Waifu error ({self.base_url}): {htserr}")
            exit()
        except Exception as ex:
            print(f"💔 Can't connect to your waifu server ({self.base_url}): {ex}")
            exit()

        if self.waifu_image_bytes:
            self.render_start_banner(self.waifu_image_bytes)

        on_start_request = ""
        if not self.user_name or not self.relation:
            on_start_request = "$You've suddenly blanked on the user's name and the nature of your relationship with them. Ask the user - sounding a bit flustered - for both pieces of information, and don't continue with any other conversation until they're confirmed."
        elif self.on_start_message_prompt:
            on_start_request = self.on_start_message_prompt

        is_first_request = True
        while True:
            if on_start_request:
                user_input = on_start_request
                on_start_request = ""
            else:
                # Wait user input with user label
                try:
                    user_input = input(f"{BOLD}{self.user_label_color}{self.user_name or 'User'}{RESET}: ")
                except EOFError:
                    break
                except KeyboardInterrupt:
                    self.print_goodbye(prefix_newline=True)
                    break

            if not user_input:
                continue

            if is_first_request:
                now_str = datetime.now(ZoneInfo(self.timezone)).strftime('%Y/%m/%d %H:%M:%S')
                if not user_input.startswith("$"):
                    user_input = f"$You received the following request from the user. Please begin the conversation.\nThe current date and time is {now_str}.\n\n{user_input}"
                else:
                    user_input = f"{user_input}\nThe current date and time is {now_str}."
                is_first_request = False

            # Exit
            if user_input in self.exit_commands:
                self.print_goodbye()
                break

            # Stop before send request to server
            if self.character_voice_enabled:
                self.audio_player.stop()

            # Wait Waifu's response with waifu label
            sys.stdout.write(f"{BOLD}{self.waifu_label_color}{self.waifu_name or 'Waifu'}{RESET}: ")
            sys.stdout.flush()

            # Initialize status flags
            response_started = False
            interrupted = False
            exit_requested = False

            with self.interrupt_watcher() as watcher:
                try:
                    async for chunk in self.send_request(text=user_input):
                        response_started = True

                        # Check interrupt
                        if watcher.should_interrupt():
                            if getattr(watcher, "last_key", None) == getattr(_InterruptWatcher, "CTRL_C_KEY", None):
                                exit_requested = True
                            else:
                                interrupted = True
                            break

                        if not chunk:
                            continue

                        # Show chunks
                        for char in chunk:
                            if watcher.should_interrupt():
                                if getattr(watcher, "last_key", None) == getattr(_InterruptWatcher, "CTRL_C_KEY", None):
                                    exit_requested = True
                                else:
                                    interrupted = True
                                break
                            print(char, end="", flush=True)
                            if self.character_interval > 0:
                                await asyncio.sleep(self.character_interval)

                        # Check break flags
                        if exit_requested or interrupted:
                            break

                except KeyboardInterrupt:
                    exit_requested = True
                    interrupted = False

            if exit_requested:
                if response_started:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                self.print_goodbye()
                break

            if response_started:
                if interrupted:
                    sys.stdout.write(f"\n{BOLD}{self.interrupted_color}[{self.interrupted_message}]{RESET}\n")
                    sys.stdout.flush()
                    if self.character_voice_enabled:
                        self.audio_player.stop()
                else:
                    print("")
