import base64
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
from pathlib import Path
from typing import AsyncGenerator
from uuid import uuid4
import httpx
import openai
from entities import UserRepository, WaifuRepository, Waifu
from prompt import PromptBuilder

logger = logging.getLogger(__name__)


class WaifuService:
    IMAGE_GENERATION_PROMPT_BASE = """与えられたキャラクター設定に相応しいSNSアイコン画像を生成してください。

## 基本ルール

- 日本のアニメキャラクター風
- アスペクト比は1:1
- 色温度は5500K

{CHARACTER_PROMPT}
"""

    def __init__(
        self,
        *,
        data_dir: str,
        waifu_repo: WaifuRepository,
        user_repo: UserRepository,
        prompt_builder: PromptBuilder,
        openai_api_key: str,
        openai_base_url: str,
        openai_model: str,
        openai_reasoning_effort: str,
        timezone: str
    ):
        self.data_dir = data_dir
        self.waifu_repo = waifu_repo
        self.current_waifu = waifu_repo.get_waifu()
        self.user_repo = user_repo
        self.prompt_builder = prompt_builder
        self.client = openai.AsyncClient(
            api_key=openai_api_key,
            base_url=openai_base_url,
            timeout=120.0
        )
        self.openai_api_key = openai_api_key
        self.openai_model = openai_model
        self.openai_reasoning_effort = openai_reasoning_effort
        self.timezone = timezone

        self._on_waifu_activated: callable = None
        self._on_waifu_updated: callable = None

    async def generate_image(self, character_prompt: str, additional_info: str):
        image_generation_prompt = self.IMAGE_GENERATION_PROMPT_BASE.format(CHARACTER_PROMPT=character_prompt)
        logger.info(f"Image generation prompt: {image_generation_prompt} (len={len(bytes(image_generation_prompt, encoding='utf-8'))})")

        # Generate image
        image_bytes = None
        if "grok" in self.openai_model:
            resp = await self.client.images.generate(
                model="grok-2-image-latest",
                prompt=image_generation_prompt,
                response_format="b64_json"
            )
            image_base64 = resp.data[0].b64_json
            image_bytes = base64.b64decode(image_base64)
        elif "gemini" in self.openai_model:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    url="https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent",
                    headers={
                        "x-goog-api-key": self.openai_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [{
                            "parts": [{"text": image_generation_prompt}]
                        }],
                        "generationConfig": {
                            "imageConfig": {
                                "aspectRatio": "1:1",
                                "imageSize": "1K"
                            }
                        }
                    }
                )
                image_base64 = None
                for p in resp.json()["candidates"][0]["content"]["parts"]:
                    if inline_data := p.get("inlineData"):
                        image_base64 = inline_data["data"]
                        break
                image_bytes = base64.b64decode(image_base64)
        else:
            resp = await self.client.images.generate(
                model="gpt-image-1",
                prompt=image_generation_prompt,
                size="1024x1024"
            )
            image_base64 = resp.data[0].b64_json
            image_bytes = base64.b64decode(image_base64)

        return image_generation_prompt, image_bytes

    def get_image(self, waifu_id: str):
        with open(f"{self.data_dir}/waifus/{waifu_id}/icon.png", "rb") as f:
            character_image_bytes = f.read()
        return character_image_bytes

    def update_image(self, waifu_id: str, image_bytes: bytes):
        with open(f"{self.data_dir}/waifus/{waifu_id}/icon.png", "wb") as f:
            f.write(image_bytes)

    async def create(
        self,
        *,
        character_name: str,
        character_description: str,
        speech_service: str,
        speaker: str
    ) -> AsyncGenerator:
        waifu_id = f"waifu_{uuid4()}"
        progress = ""

        try:
            progress = "initializing"

            # Create waifu asset dir
            waifu_dir_path = Path(f"{self.data_dir}/waifus/{waifu_id}")
            waifu_dir_path.mkdir(parents=True, exist_ok=True)

            # Generate prompts
            progress = "creating character prompt"
            character_prompt = await self.prompt_builder.generate_character_prompt(
                waifu_id=waifu_id,
                character_name=character_name,
                character_description=character_description
            )
            yield character_prompt, "character_prompt"

            progress = "creating weekly plan"
            weekly_plan_prompt = await self.prompt_builder.generate_weekly_plan_prompt(
                waifu_id=waifu_id,
                character_prompt=character_prompt
            )
            yield weekly_plan_prompt, "weekly_plan_prompt"

            progress = "creating daily plan"
            daily_plan_prompt = await self.prompt_builder.generate_daily_plan_prompt(
                waifu_id=waifu_id,
                character_prompt=character_prompt,
                weekly_plan_prompt=weekly_plan_prompt
            )
            yield daily_plan_prompt, "daily_plan_prompt"

            # Generate image
            progress = "creating icon image"
            image_bytes = None
            try:
                image_generation_prompt, image_bytes = await self.generate_image(
                    character_prompt,
                    additional_info=""
                )
            except Exception:
                logger.exception(f"Error at generating icon image.")

            if not image_bytes:
                yield "Error in generating icon. Use default icon instead.", "warning"
                with open(f"{self.data_dir}/default_icon.png", "rb") as f:
                    image_bytes = f.read()

            with open(waifu_dir_path / "icon.png", "wb") as f:
                f.write(image_bytes)
                yield image_bytes, "image_bytes"

            # Update database
            progress = "activating waifu"
            self.waifu_repo.update_waifu(
                waifu_id=waifu_id,
                waifu_name=character_name,
                is_active=False,
                speech_service=speech_service,
                speaker=speaker,
                birthday_mmdd=datetime.now(ZoneInfo(self.timezone)).strftime("%m%d"),
                metadata={}
            )

            # Activate
            yield await self.activate(waifu_id=waifu_id), "final"

        except Exception as ex:
            logger.exception(f"Error in creating waifu: progress={progress}")
            yield f"Error in creating waifu: progress={progress}", "error"

    async def activate(self, waifu_id: str) -> Waifu:
        waifu = self.waifu_repo.get_waifu(waifu_id=waifu_id)
        if not waifu:
            raise Exception(f"waifu not found: waifu_id={waifu_id}")

        # Make today's plan prompt if it doesn't exist
        if not self.prompt_builder.get_daily_plan_prompt_path(waifu_id=waifu_id).exists():
            await self.prompt_builder.generate_daily_plan_prompt(
                waifu_id=waifu.waifu_id,
                character_prompt=self.prompt_builder.get_character_prompt(waifu_id=waifu.waifu_id),
                weekly_plan_prompt=self.prompt_builder.get_weekly_plan_prompt(waifu_id=waifu.waifu_id)
            )

        # Activate
        activated_waifu = self.waifu_repo.update_waifu(
            waifu_id=waifu.waifu_id,
            is_active=True
        )

        # Change current waifu
        waifu.is_active = True
        self.current_waifu = waifu

        if self._on_waifu_activated:
            await self._on_waifu_activated(activated_waifu)

        return activated_waifu

    async def update(
        self,
        waifu_id: str,
        waifu_name: str = None,
        speech_service: str = None,
        speaker: str = None,
        birthday_mmdd: str = None,
        metadata: dict = None
    ) -> Waifu:
        waifu = self.waifu_repo.get_waifu(waifu_id=waifu_id)
        if not waifu:
            raise Exception(f"waifu not found: waifu_id={waifu_id}")

        # Update
        updated_waifu = self.waifu_repo.update_waifu(
            waifu_id=waifu_id,
            waifu_name=waifu_name,
            speech_service=speech_service,
            speaker=speaker,
            birthday_mmdd=birthday_mmdd,
            metadata=metadata or {}
        )

        if self._on_waifu_updated:
            await self._on_waifu_updated(updated_waifu)

        return updated_waifu

    def on_waifu_activated(self, func):
        self._on_waifu_activated = func
        return func

    def on_waifu_updated(self, func):
        self._on_waifu_updated = func
        return func

    @property
    def character_prompt(self) -> str:
        return self.prompt_builder.get_character_prompt(self.current_waifu.waifu_id)

    @property
    def weekly_plan_prompt(self) -> str:
        return self.prompt_builder.get_weekly_plan_prompt(self.current_waifu.waifu_id)

    @property
    def daily_plan_prompt(self) -> str:
        return self.prompt_builder.get_daily_plan_prompt(self.current_waifu.waifu_id)

    @property
    def image(self) -> bytes:
        return self.get_image(self.current_waifu.waifu_id)

    def get_system_prompt(self, context_id: str, user_id: str, system_prompt_params: dict) -> str:
        user = self.user_repo.get_user(user_id=user_id, waifu_id=self.current_waifu.waifu_id)
        return self.prompt_builder.get_system_prompt(
            waifu_id=self.current_waifu.waifu_id,
            system_prompt_params={"user_name": user.user_name or "User", "relation": user.relation or "unknown"}
        )
