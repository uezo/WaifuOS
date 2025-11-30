from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import List
import openai

logger = logging.getLogger(__name__)


class DiaryManager:
    TOPIC_PROMPT = """日記を書く前に、本日の出来事から日記に書くべき主要な出来事やトピックを挙げてください。
このキャラクターの価値観に照らして、特に感じたこと・考えたことがありそうなものを選定すること。
    
{daily_activity}
    
{additional_contents}
"""

    GENERATION_PROMPT = """挙げたトピックに従い、800字以内程度で日記を書いてください。
タイトルは「## {date_str}の日記」と1行目に出力してください。

日記は、トピック毎にその出来事の概要と、それについてキャラクターが感じたこと・考えたことを端的にまとめた形式とする。

なお昨日の日記は以下の通り。必要に応じて関連づけつつ、あまり似通った内容にならないようにしてください。

{last_diary}
"""

    def __init__(
        self,
        *,
        data_dir: str,
        openai_api_key: str,
        openai_base_url: str,
        openai_model: str,
        openai_reasoning_effort: str,
        debug: bool = False
    ):
        self.data_dir = data_dir
        self.client = openai.AsyncClient(
            api_key=openai_api_key,
            base_url=openai_base_url,
            timeout=120.0
        )
        self.openai_model = openai_model
        self.openai_reasoning_effort = openai_reasoning_effort
        self.debug = debug

    async def generate_diary(
        self,
        *,
        waifu_id: str,
        character_prompt: str,
        daily_activity: str,
        additional_contents: List[str],
        target_date: datetime
    ) -> str:
        # NOTE: Conversation history is not used since it varies by user.

        # Pick up impressive topics
        user_content_for_initialize = self.TOPIC_PROMPT.format(
            daily_activity=daily_activity,
            additional_contents="\n\n".join(additional_contents)
        )
        messages = [
            {"role": "system", "content": f"以下のキャラクター設定に従って日記を書いてください。\n\n{character_prompt}"},
            {"role": "user", "content": user_content_for_initialize}
        ]
        topics_resp = await self.client.chat.completions.create(
            model=self.openai_model,
            reasoning_effort=self.openai_reasoning_effort or openai.NOT_GIVEN,
            messages=messages
        )
        topics = topics_resp.choices[0].message.content
        if self.debug:
            logger.info(f"Topics for diary: {topics}")
        messages.append({"role": "assistant", "content": topics})

        # Generate diary
        last_diary = self.get_diary(
            waifu_id=waifu_id,
            target_date=target_date - timedelta(days=1)
        ) or "昨日の日記なし"
        messages.append({
            "role": "user",
            "content": self.GENERATION_PROMPT.format(
                date_str=target_date.strftime("%Y/%m/%d (%a)"),
                last_diary=last_diary
            )
        })
        diary_resp = await self.client.chat.completions.create(
            model=self.openai_model,
            reasoning_effort=self.openai_reasoning_effort or openai.NOT_GIVEN,
            messages=messages
        )
        if self.debug:
            logger.info(f"Diary generation request: {messages[-1]['content']}")
        diary_body = diary_resp.choices[0].message.content
        if self.debug:
            logger.info(f"Diary: {diary_body}")

        # Save
        if diary_body:
            with open(self.get_diary_path(waifu_id=waifu_id, target_date=target_date), "w") as f:
                f.write(diary_body)
        
        return diary_body

    def get_diary(self, waifu_id: str, target_date: datetime):
        diary_path = self.get_diary_path(waifu_id=waifu_id, target_date=target_date)
        if diary_path.exists():
            with open(diary_path, "r") as f:
                return f.read()
        else:
            return None

    def get_diary_path(self, waifu_id: str, target_date: datetime) -> Path:
        diary_dir_path = Path(f"{self.data_dir}/waifus/{waifu_id}/diaries")
        diary_dir_path.mkdir(exist_ok=True)
        return diary_dir_path / f"{target_date.strftime('%Y%m%d')}.md"
