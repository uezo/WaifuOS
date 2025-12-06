from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
from pathlib import Path
from typing import List
import openai

logger = logging.getLogger(__name__)


class PromptBuilder:
    CHARACTER_GENERATION_PROMPT = """
与えられた情報からキャラクター設定を考えてください。
キャラクター設定は以下のマークダウンで示された項目を埋めたものとしてください。
出力はマークダウン部分のみとします。
セリフ例には鉤括弧や記号、絵文字、ト書きを含む例文は使用不可。


## キャラクター設定

- 名前: {character_name}
- 性別:
- 年齢:
- 職業・所属:
- 髪型や見た目の特徴:
- 性格:
- 趣味・ハマっていること:
- 好きなもの:
- 嫌いなもの:
- その他の情報:


## 話し方

- 一人称:
- 語尾・ですます調・タメ語等:
- 表情変化の豊かさ:
- その他の特徴:


## セリフ例


"""

    WEEKLY_PLAN_GENERATION_PROMPT = """
与えられたキャラクター設定に相応しい1週間のスケジュールを1時間単位でマークダウンのテーブルで出力してください。
授業の教科など含め可能な限り詳細かつ端的に。
日によりアクティビティーの異なる時間帯は「自由時間」とすること。
出力はマークダウンのテーブル部分のみとする。
"""

    DAILY_PLAN_GENERATION_SYSTEM_PROMPT = """
以下のキャラクター設定に基づき、与えられた週間スケジュールから{today}のスケジュールを生成してください。
自由時間など行動予定が決まっていない部分があれば、具体的な予定を考えて埋めてください。
出力フォーマットはマークダウンで、タイトルは「## YYYY月MM月DD日 (曜日)の活動」、予定の内容はテーブル形式とします。

{character_prompt}

{additional_contents}
"""

    DAILY_PLAN_GENERATION_USER_PROMPT = """
週間予定は以下の通り。

{weekly_plan_prompt}


週間予定に基づき、以下のフォーマットで出力してください。タイトルとテーブルのみを出力すること。


## YYYY月MM月DD日 (曜日)の活動

| 時間帯 | 活動 |
|--------|------|
| 0:00-1:00 | |
| 1:00-2:00 | |
| 2:00-3:00 | |
| 3:00-4:00 | |
| 4:00-5:00 | |
| 5:00-6:00 | |
| 6:00-7:00 | |
| 7:00-8:00 | |
| 8:00-9:00 | |
| 9:00-10:00 | |
| 10:00-11:00 | |
| 11:00-12:00 | |
| 12:00-13:00 | |
| 13:00-14:00 | |
| 14:00-15:00 | |
| 15:00-16:00 | |
| 16:00-17:00 | |
| 17:00-18:00 | |
| 18:00-19:00 | |
| 19:00-20:00 | |
| 20:00-21:00 | |
| 21:00-22:00 | |
| 22:00-23:00 | |
| 23:00-24:00 | |
"""

    def __init__(
        self,
        *,
        data_dir: str,
        openai_api_key: str,
        openai_base_url: str,
        openai_model: str,
        openai_reasoning_effort: str,
        day_boundary_time: int,
        timezone: str,
        debug: bool = False,
    ):
        self.data_dir = data_dir
        self.client = openai.AsyncClient(
            api_key=openai_api_key,
            base_url=openai_base_url,
            timeout=120.0
        )
        self.openai_model = openai_model
        self.openai_reasoning_effort = openai_reasoning_effort
        self.day_boundary_time = day_boundary_time
        self.timezone = timezone
        self.debug = debug

        self.character_prompt_timestamps = {}
        self.character_prompts = {}
        self.plan_weekly_prompt_timestamps = {}
        self.plan_weekly_prompts = {}
        self.plan_daily_prompt_timestamps = {}
        self.plan_daily_prompts = {}
        self.base_prompt_timestamp = datetime.min
        self.base_prompt: str = None

    async def generate(self, system_content: str, user_content: str, save_path: str = None):
        resp = await self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            model=self.openai_model,
            reasoning_effort=self.openai_reasoning_effort or openai.NOT_GIVEN
        )
        prompt = resp.choices[0].message.content
        if save_path:
            with open(save_path, "w") as f:
                f.write(prompt)
        return prompt

    async def generate_character_prompt(self, waifu_id: str, character_name: str, character_description: str) -> str:
        return await self.generate(
            system_content=self.CHARACTER_GENERATION_PROMPT,
            user_content=f"Character Name: {character_name}\nCharacter Description:\n{character_description}",
            save_path=f"{self.data_dir}/waifus/{waifu_id}/character_prompt.md"
        )

    async def generate_weekly_plan_prompt(self, waifu_id: str, character_prompt: str):
        return await self.generate(
            system_content=self.WEEKLY_PLAN_GENERATION_PROMPT,
            user_content=character_prompt,
            save_path=f"{self.data_dir}/waifus/{waifu_id}/plan_weekly_prompt.md"
        )

    async def generate_daily_plan_prompt(
        self,
        *,
        waifu_id: str,
        additional_contents: List[str],
        target_date: datetime = None,
    ):
        today = target_date or datetime.now(ZoneInfo(self.timezone))
        user_content = self.DAILY_PLAN_GENERATION_USER_PROMPT.format(
            weekly_plan_prompt=self.get_weekly_plan_prompt(waifu_id=waifu_id)
        )
        if self.debug:
            logger.info(f"Daily plan generation request: {user_content}")

        return await self.generate(
            system_content=self.DAILY_PLAN_GENERATION_SYSTEM_PROMPT.format(
                today=today,
                character_prompt=self.get_character_prompt(waifu_id=waifu_id),
                additional_contents="\n\n".join(additional_contents)
            ),
            user_content=user_content,
            save_path=self.get_daily_plan_prompt_path(waifu_id=waifu_id, target_date=target_date)
        )

    def get_character_prompt(self, waifu_id: str):
        character_prompt_path = Path(f"{self.data_dir}/waifus/{waifu_id}/character_prompt.md")
        prompt_timestamp = datetime.fromtimestamp(character_prompt_path.stat().st_mtime)
        if prompt_timestamp > self.character_prompt_timestamps.get(waifu_id, datetime.min):
            with open(character_prompt_path, "r") as f:
                self.character_prompts[waifu_id] = f.read()
            self.character_prompt_timestamps[waifu_id] = prompt_timestamp
            logger.info(f"Character prompt reloaded from {character_prompt_path}")
        return self.character_prompts[waifu_id]

    def get_weekly_plan_prompt(self, waifu_id: str):
        plan_weekly_prompt_path = Path(f"{self.data_dir}/waifus/{waifu_id}/plan_weekly_prompt.md")
        prompt_timestamp = datetime.fromtimestamp(plan_weekly_prompt_path.stat().st_mtime)
        if prompt_timestamp > self.plan_weekly_prompt_timestamps.get(waifu_id, datetime.min):
            with open(plan_weekly_prompt_path, "r") as f:
                self.plan_weekly_prompts[waifu_id] = f.read()
            self.plan_weekly_prompt_timestamps[waifu_id] = prompt_timestamp
            logger.info(f"Weekly plan prompt reloaded from {plan_weekly_prompt_path}")
        return self.plan_weekly_prompts[waifu_id]

    def get_daily_plan_prompt(self, waifu_id: str, target_date: datetime = None):
        plan_daily_prompt_path = self.get_daily_plan_prompt_path(waifu_id=waifu_id, target_date=target_date)
        if not plan_daily_prompt_path.exists():
            return None
        
        if target_date:
            with open(plan_daily_prompt_path, "r") as f:
                return f.read()

        prompt_timestamp = datetime.fromtimestamp(plan_daily_prompt_path.stat().st_mtime)
        if prompt_timestamp > self.plan_daily_prompt_timestamps.get(waifu_id, datetime.min):
            with open(plan_daily_prompt_path, "r") as f:
                self.plan_daily_prompts[waifu_id] = f.read()
            self.plan_daily_prompt_timestamps[waifu_id] = prompt_timestamp
            logger.info(f"Daily plan prompt reloaded from {plan_daily_prompt_path}")
        return self.plan_daily_prompts[waifu_id]

    def get_base_prompt(self):
        base_prompt_path = Path(f"{self.data_dir}/system_prompt_base.md")
        prompt_timestamp = datetime.fromtimestamp(base_prompt_path.stat().st_mtime)
        if prompt_timestamp > self.base_prompt_timestamp:
            with open(base_prompt_path, "r") as f:
                self.base_prompt = f.read()
            self.base_prompt_timestamp = prompt_timestamp
            logger.info(f"Base prompt reloaded from {base_prompt_path}")
        return self.base_prompt

    def get_system_prompt(self, waifu_id: str, system_prompt_params: dict):
        system_prompt = self.get_base_prompt().format(
            character_prompt=self.get_character_prompt(waifu_id=waifu_id),
            plan_prompt=self.get_daily_plan_prompt(waifu_id=waifu_id)
        )

        return system_prompt.format(**system_prompt_params)

    def get_daily_plan_prompt_path(self, waifu_id: str, target_date: datetime = None) -> Path:
        target_date = target_date or datetime.now(ZoneInfo(self.timezone)) - timedelta(hours=self.day_boundary_time)
        daily_plan_dir_path = Path(f"{self.data_dir}/waifus/{waifu_id}/plan_daily_prompts")
        daily_plan_dir_path.mkdir(exist_ok=True)
        return daily_plan_dir_path / f"{target_date.strftime('%Y%m%d')}.md"

    def update_weekly_plan_prompt(self, waifu_id: str, weekly_plan_prompt: str) -> str:
        plan_weekly_prompt_path = Path(f"{self.data_dir}/waifus/{waifu_id}/plan_weekly_prompt.md")
        with open(plan_weekly_prompt_path, "w") as f:
            f.write(weekly_plan_prompt)
        return weekly_plan_prompt

    def update_daily_plan_prompt(self, waifu_id: str, daily_plan_prompt: str, target_date: datetime = None) -> str:
        plan_daily_prompt_path = self.get_daily_plan_prompt_path(waifu_id=waifu_id, target_date=target_date)
        with open(plan_daily_prompt_path, "w") as f:
            f.write(daily_plan_prompt)
        return daily_plan_prompt
