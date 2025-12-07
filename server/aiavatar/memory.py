import asyncio
from datetime import datetime
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
import httpx
from aiavatar.sts.models import STSRequest, STSResponse

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    answer: Optional[str]
    retrieved_data: Optional[str]

class ChatMemoryClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        *,
        top_k: int = 5,
        search_content: bool = False,
        include_retrieved_data: bool = False,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        timeout: float = 60.0,
        debug: bool = False
    ):
        self.base_url = base_url
        self.top_k = top_k
        self.search_content = search_content
        self.include_retrieved_data = include_retrieved_data
        self.http_client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections
            )
        )
        self.debug = debug
        self.debug = True

        self._queue: asyncio.Queue[Tuple[STSRequest, STSResponse]] = asyncio.Queue()
        self._worker_task = asyncio.create_task(self._process_queue())

    async def search(self, user_id: str, waifu_id: str, query: str, since: str = None, until: str = None) -> SearchResult:
        if not user_id or not waifu_id or not query:
            return SearchResult(answer=None, retrieved_data=None)

        if self.debug:
            logger.info(f"ChatMemory.search: user_id={user_id} / query={query} / since={since} / until={until}")

        try:
            resp = await self.http_client.post(
                url=f"{self.base_url}/search",
                json={
                    "user_id": user_id + "_" + waifu_id,
                    "query": query,
                    "top_k": self.top_k,
                    "search_content": self.search_content,
                    "include_retrieved_data": self.include_retrieved_data,
                    "since": since,
                    "until": until
                }
            )
            resp.raise_for_status()
            resp_json = resp.json()

            if self.debug:
                logger.info(f"ChatMemory.search: result={resp_json} ")

            return SearchResult(
                answer=resp_json["result"]["answer"],
                retrieved_data=resp_json["result"]["retrieved_data"]
            )

        except Exception as ex:
            logger.exception(f"Error at search ChatMemory: {ex}")
            raise ex

    # Message history
    async def add_messages(self, request: STSRequest, response: STSResponse, waifu_id: str):
        if not request.user_id or not request.context_id or not request.text or not response.voice_text or not waifu_id:
            return

        try:
            resp = await self.http_client.post(
                url=f"{self.base_url}/history",
                json={
                    "user_id": request.user_id + "_" + waifu_id,
                    "session_id": request.context_id,
                    "messages": [
                        {"role": "user", "content": request.text},
                        {"role": "assistant", "content": response.voice_text}
                    ]
                }
            )
            resp.raise_for_status()

        except Exception as ex:
            logger.exception(f"Error at add_messages to ChatMemory: {ex}")
            raise ex

    async def _process_queue(self):
        while True:
            request, response, waifu_id = await self._queue.get()
            try:
                await self.add_messages(request, response, waifu_id)
            except Exception as ex:
                logger.exception(f"Error processing queued messages: {ex}")
            finally:
                self._queue.task_done()

    async def enqueue_messages(self, request: STSRequest, response: STSResponse, waifu_id: str):
        await self._queue.put((request, response, waifu_id))

    # Diary
    async def get_diary(self, waifu_id: str, target_date: datetime) -> str:
        resp = await self.http_client.get(
            url=f"{self.base_url}/diary",
            params={
                "user_id": waifu_id,
                "diary_date": target_date.strftime("%Y-%m-%d")
            }
        )
        logger.warning(resp.json())
        return resp.json()["diaries"][0]["content"]

    async def update_diary(self, waifu_id: str, content: str, target_date: datetime):
        resp = await self.http_client.post(
            url=f"{self.base_url}/diary",
            json={
                "user_id": waifu_id,
                "content": content,
                "diary_date": target_date.strftime("%Y-%m-%d")
            }
        )
        return resp.json()
