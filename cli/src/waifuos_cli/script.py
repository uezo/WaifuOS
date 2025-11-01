import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import webbrowser
from dotenv import load_dotenv, set_key
import httpx
from . import WaifuCLI
from .create import WaifuCreator
from .switch import WaifuSwitcher
from .alias import create_alias as create_alias_subcommand


# Get configurations
base_path = Path("~/.waifucli").expanduser()
if not base_path.exists():
    base_path.mkdir(mode=0o700, parents=True, exist_ok=True)

def normalize_command_name(raw_command: str) -> str:
    name = Path(raw_command).name
    # Strip pip-generated helpers like "-script.py" first.
    if name.endswith("-script.py"):
        name = name[: -len("-script.py")]
    # Remove simple suffixes (exe/cmd/bat/py/sh).
    suffixes = [".exe", ".cmd", ".bat", ".py", ".sh"]
    lowered = name.lower()
    for suffix in suffixes:
        if lowered.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name

command_name = normalize_command_name(sys.argv[0])
default_env_path = base_path / "default.env"
if not default_env_path.exists():
    set_key(str(default_env_path), "BASE_URL", "http://127.0.0.1:8012/aiavatar/api")
load_dotenv(default_env_path, override=False)
if command_name != "waifu":
    load_dotenv(base_path / f"{command_name}.env", override=True)

# Configure logger
LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING")
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)
log_format = logging.Formatter("[%(levelname)s] %(asctime)s : %(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_format)
logger.addHandler(stream_handler)


class WaifuScript:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.waifu_creator: WaifuCreator = None
        self.waifu_switcher: WaifuSwitcher = None

    def create_waifu(self):
        if not self.waifu_creator:
            self.waifu_creator = WaifuCreator(base_url=self.base_url)
        self.waifu_creator.start_wizard()

    def switch_waifu(self, args: list[str]):
        if len(args) > 0:
            parser = argparse.ArgumentParser(
                prog="waifu switch",
                description="Create an additional command name that launches waifucli.",
            )
            parser.add_argument(
                "waifu_id",
                help="Id of the waifu to switch to (e.g. 'waifu_98b0e6c2-678a-4ecb-8102-3daaef0ff431')."
            )
            options = parser.parse_args(args)
            waifu_id = options.waifu_id
        else:
            waifu_id = None

        if not self.waifu_switcher:
            self.waifu_switcher = WaifuSwitcher(base_url=self.base_url)
        self.waifu_switcher.switch_waifu(waifu_id=waifu_id)

    def create_alias(self, main_command: str, args: list[str]):
        parser = argparse.ArgumentParser(
            prog="waifu alias",
            description="Create an additional command name that launches waifucli.",
        )
        parser.add_argument("name", help="Alias command name to create (e.g. 'isuzu').")
        parser.add_argument(
            "--dir",
            dest="directory",
            help="Directory to place the alias. Defaults to the directory of the existing waifu command.",
        )
        parser.add_argument(
            "--copy",
            action="store_true",
            help="Force copying the launcher instead of creating a symlink.",
        )
        options = parser.parse_args(args)

        try:
            alias_path = create_alias_subcommand(
                waifu_command_path=main_command,
                alias_name=options.name,
                target_dir=options.directory,
                prefer_copy=options.copy,
            )
        except Exception as exc:
            raise SystemExit(f"Failed to create alias '{options.name}': {exc}") from exc

        print(f"Alias '{options.name}' created at {alias_path}")

    def open_browser(self, user_id: str):
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                url=self.base_url + "/cli-web-bridge/start",
                json={
                    "user_id": user_id
                }
            )
            resp.raise_for_status()
            data = resp.json()
            try:
                webbrowser.open(self.base_url + data["link"])
            except Exception:
                logger.exception("Error in opening browser")

    def main(self, sys_argv: list):
        args = sys_argv[1:]
        if args:
            if args[0] == "create":
                self.create_waifu()
                return
            if args[0] == "switch":
                self.switch_waifu(args[1:])
                return
            if args[0] == "alias":
                self.create_alias(sys_argv[0], args[1:])
                return
            if args[0] == "browser":
                self.open_browser(user_id=os.getenv("USER_ID"))
                return

        cli_args = {"default_env_path": default_env_path, "base_url": self.base_url}

        if api_key := os.getenv("API_KEY"):
            cli_args["api_key"] = api_key

        if user_id := os.getenv("USER_ID"):
            cli_args["user_id"] = user_id

        if on_start_message_prompt := os.getenv("ON_START_MESSAGE_PROMPT"):
            cli_args["on_start_message_prompt"] = on_start_message_prompt

        if timezone := os.getenv("TIMEZONE"):
            cli_args["timezone"] = timezone

        if (character_voice_enabled := os.getenv("CHARACTER_VOICE_ENABLED")) is not None:
            cli_args["character_voice_enabled"] = character_voice_enabled.lower() in {"1", "true", "yes", "on"}

        if faces := os.getenv("FACES"):
            try:
                cli_args["faces"] = json.loads(faces)
            except json.JSONDecodeError:
                logger.warning("FACES must be a valid JSON object, got %s; ignoring", faces)

        try:
            cli_args["character_interval"] = float(os.getenv("CHARACTER_INTERVAL", "0.02"))
        except ValueError as exc:
            logger.warning("Invalid CHARACTER_INTERVAL: %s", exc)

        if (icon_width_ratio := os.getenv("ICON_WIDTH_RATIO")) is not None:
            try:
                cli_args["icon_width_ratio"] = float(icon_width_ratio)
            except ValueError:
                logger.warning("ICON_WIDTH_RATIO must be a float, got %s; ignoring", icon_width_ratio)

        if (icon_max_width := os.getenv("ICON_MAX_WIDTH")) is not None:
            try:
                cli_args["icon_max_width"] = int(icon_max_width)
            except ValueError:
                logger.warning("ICON_MAX_WIDTH must be an integer, got %s; ignoring", icon_max_width)

        if (icon_min_width := os.getenv("ICON_MIN_WIDTH")) is not None:
            try:
                cli_args["icon_min_width"] = int(icon_min_width)
            except ValueError:
                logger.warning("ICON_MIN_WIDTH must be an integer, got %s; ignoring", icon_min_width)

        if (icon_aspect_ratio := os.getenv("ICON_ASPECT_RATIO")) is not None:
            try:
                cli_args["icon_aspect_ratio"] = float(icon_aspect_ratio)
            except ValueError:
                logger.warning("ICON_ASPECT_RATIO must be a float, got %s; ignoring", icon_aspect_ratio)

        if (use_truecolor := os.getenv("USE_TRUECOLOR")) is not None:
            cli_args["use_truecolor"] = use_truecolor.lower() in {"1", "true", "yes", "on"}
        else:
            if os.getenv("COLORTERM", "") == "truecolor":
                cli_args["use_truecolor"] = True

        if waifu_label_color := os.getenv("WAIFU_LABEL_COLOR"):
            cli_args["waifu_label_color"] = waifu_label_color

        if user_label_color := os.getenv("USER_LABEL_COLOR"):
            cli_args["user_label_color"] = user_label_color

        if face_color := os.getenv("FACE_COLOR"):
            cli_args["face_color"] = face_color

        if (timeout_value := os.getenv("TIMEOUT")) is not None:
            try:
                cli_args["timeout"] = float(timeout_value)
            except ValueError:
                logger.warning("TIMEOUT must be a float, got %s; ignoring", timeout_value)

        if (output_device_index := os.getenv("OUTPUT_DEVICE_INDEX")) is not None:
            try:
                cli_args["output_device_index"] = int(output_device_index)
            except ValueError:
                logger.warning("OUTPUT_DEVICE_INDEX must be an integer, got %s; ignoring", output_device_index)

        if (output_chunk_size := os.getenv("OUTPUT_CHUNK_SIZE")) is not None:
            try:
                cli_args["output_chunk_size"] = int(output_chunk_size)
            except ValueError:
                logger.warning("OUTPUT_CHUNK_SIZE must be an integer, got %s; ignoring", output_chunk_size)

        if (debug_value := os.getenv("DEBUG")) is not None:
            cli_args["debug"] = debug_value.lower() in {"1", "true", "yes", "on"}

        waifu_cli = WaifuCLI(**cli_args)

        try:
            asyncio.run(waifu_cli.start())
        except KeyboardInterrupt:
            pass


def main():
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8012/aiavatar/api")
    waifu_script = WaifuScript(base_url=base_url)
    waifu_script.main(sys.argv)
