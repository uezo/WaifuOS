from abc import ABC, abstractmethod
from datetime import datetime
from zoneinfo import ZoneInfo
from logging import getLogger
import httpx
from aiavatar.sts.llm import LLMService, Tool
from aiavatar.sts.llm.tools.openai_websearch import OpenAIWebSearchTool
from entities import UserRepository
from service import WaifuService
from memory import ChatMemoryClient

logger = getLogger(__name__)


# Web Search Tools
class WebSearchTool(Tool, ABC):
    @abstractmethod
    async def search(self, query: str):
        pass


class GrokWebSearchTool(WebSearchTool):
    def __init__(
        self,
        *,
        xai_api_key: str,
        model: str = "grok-4-fast-non-reasoning-latest",
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        timeout: float = 60.0,
        name=None,
        spec=None,
        instruction = None,
        is_dynamic = False,
        debug: bool = False
    ):
        self.http_client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections
            )
        )
        self.xai_api_key = xai_api_key
        self.model = model
        self.debug = debug

        super().__init__(
            name or "web_search",
            spec or {
                "type": "function",
                "function": {
                    "name": name or "web_search",
                    "description": "Search the web using Grok WebSearch",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    },
                }
            },
            self.search,
            instruction,
            is_dynamic
        )

    async def search(self, query: str):
        if self.debug:
            logger.info(f"Grok Search Query: {query}")

        resp = await self.http_client.post(
            url="https://api.x.ai/v1/responses",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.xai_api_key}"
            },
            json={
                "model": self.model,
                "input": [{"role": "user", "content": f"Search query: {query}"}],
                "tools": [{"type": "web_search"}]
            }
        )

        if resp.status_code != 200:
            logger.error(f"Error at Grok web search tool: {resp.read()}")
            return {"error": f"Error at Grok web search tool"}
        
        for o in resp.json()["output"]:
            if content := o.get("content"):
                if self.debug:
                    logger.warning(f"Grok Search Result: {content[0]['text']}")
                return {"search_result": content[0]["text"]}

        return {"search_result": "No search results"}


class GeminiWebSearchTool(WebSearchTool):
    def __init__(
        self,
        *,
        gemini_api_key: str,
        model: str = "gemini-2.5-flash",
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        timeout: float = 60.0,
        name=None,
        spec=None,
        instruction = None,
        is_dynamic = False,
        debug: bool = False
    ):
        self.http_client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections
            )
        )
        self.gemini_api_key = gemini_api_key
        self.model = model
        self.debug = debug

        super().__init__(
            name or "web_search",
            spec or {
                "type": "function",
                "function": {
                    "name": name or "web_search",
                    "description": "Search the web using Gemini WebSearch",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    },
                }
            },
            self.search,
            instruction,
            is_dynamic
        )

    async def search(self, query: str):
        if self.debug:
            logger.info(f"Gemini Search Query: {query}")

        resp = await self.http_client.post(
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.gemini_api_key
            },
            json={
                "contents": [{"parts": [{"text": f"Search query: {query}"}]}],
                "tools": [{"google_search": {}}]
            }
        )

        if resp.status_code != 200:
            logger.error(f"Error at Gemini web search tool: {resp.read()}")
            return {"error": f"Error at Gemini web search tool"}

        search_result = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

        if self.debug:
            logger.warning(f"Grok Search Result: {search_result}")

        return {"search_result": search_result}


class ClaudeWebSearchTool(WebSearchTool):
    def __init__(
        self,
        *,
        anthropic_api_key: str,
        model: str = "claude-haiku-4-5",
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        timeout: float = 60.0,
        name=None,
        spec=None,
        instruction = None,
        is_dynamic = False,
        debug: bool = False
    ):
        self.http_client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections
            )
        )
        self.anthropic_api_key = anthropic_api_key
        self.model = model
        self.debug = debug

        super().__init__(
            name or "web_search",
            spec or {
                "name": name or "web_search",
                "description": "Search the web using Claude WebSearch",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                },
            },
            self.search,
            instruction,
            is_dynamic
        )

    async def search(self, query: str):
        if self.debug:
            logger.info(f"Claude Search Query: {query}")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01"
        }

        payload = {
            "model": self.model,
            "max_tokens": 10240,
            "messages": [
                {"role": "user", "content": f"Search query: {query}"}
            ],
            "tools": [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5
            }]
        }

        resp = await self.http_client.post(
            url="https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload
        )

        if resp.status_code != 200:
            logger.error(f"Error at Claude web search tool: {resp.read()}")
            return {"error": f"Error at Claude web search tool"}

        search_result = ""
        for c in resp.json()["content"]:
            if text := c.get("text"):
                search_result += text

        if self.debug:
            logger.info(f"Claude Search Result: {search_result}")

        if search_result:
            return {"search_result": search_result}
        else:
            return {"search_result": "No search results"}


def get_web_search_tool(openai_api_key: str, openai_base_url: str):
    if not openai_base_url:
        return OpenAIWebSearchTool(openai_api_key=openai_api_key)
    elif "api.x.ai" in openai_base_url:
        return GrokWebSearchTool(xai_api_key=openai_api_key)
    elif "google" in openai_base_url:
        return GeminiWebSearchTool(gemini_api_key=openai_api_key)
    elif "anthropic" in openai_base_url:
        return ClaudeWebSearchTool(anthropic_api_key=openai_api_key)
    else:
        return OpenAIWebSearchTool(openai_api_key=openai_api_key)


# Long-term memory tool
class RetrieveMemoryTool(Tool):
    def __init__(
        self,
        chat_memory_client: ChatMemoryClient,
        waifu_service: WaifuService,
        *,
        name: str = None,
        spec: str = None,
        instruction: str = None,
        is_dynamic: bool = False,
        debug: bool = False
    ):
        self.chat_memory_client = chat_memory_client
        self.waifu_service = waifu_service
        self.debug = debug

        super().__init__(
            name or "retrieve_memory",
            spec or {
                "type": "function",
                "function": {
                    "name": name or "retrieve_memory",
                    "description": "Retrive facts and past conversation from Long-term Memory database.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "since": {"type": "string", "description": "Start date (inclusive) of the data range to search. YYYY-MM-DD format. Date only."},
                            "until": {"type": "string", "description": "End date (inclusive) of the data range to search. YYYY-MM-DD format. Date only."}
                        },
                        "required": ["query"]
                    },
                }
            },
            self.search_memory,
            instruction,
            is_dynamic
        )

    async def search_memory(self, query: str, since: str = None, until: str = None, metadata: dict = None):
        logger.info(f"Search memory: {query}")
        result = await self.chat_memory_client.search(
            user_id=metadata["user_id"],
            waifu_id=self.waifu_service.current_waifu.waifu_id,
            query=query,
            since=since,
            until=until
        )
        logger.info(f"Search memory result: {result.__dict__}")
        return result.__dict__


class GetCurrentDatetimeTool(Tool):
    def __init__(
        self,
        *,
        timezone: str = None,
        name: str = None,
        spec: str = None,
        instruction: str = None,
        is_dynamic: bool = False,
        debug: bool = False
    ):
        self.timezone = timezone or "UTC"
        self.debug = debug

        super().__init__(
            name or "get_current_datetime",
            spec or {
                "type": "function",
                "function": {
                    "name": name or "get_current_datetime",
                    "description": "Get current date and time.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    },
                }
            },
            self.get_current_datetime,
            instruction,
            is_dynamic
        )
    
    async def get_current_datetime(self):
        now = datetime.now(ZoneInfo(self.timezone))
        return {"datetime": now.strftime("%Y/%m/%d %H:%M:%S"), "timezone": self.timezone}


class UpdateUserInfoTool(Tool):
    def __init__(
        self,
        *,
        waifu_service: WaifuService,
        user_repo: UserRepository,
        name: str = None,
        spec: str = None,
        instruction: str = None,
        is_dynamic: bool = False,
        debug: bool = False
    ):
        self.waifu_service = waifu_service
        self.user_repo = user_repo
        self.debug = debug

        super().__init__(
            name or "update_userinfo",
            spec or {
                "type": "function",
                "function": {
                    "name": name or "update_userinfo",
                    "description": "Update username and relation to the user. Use this tool when the user says 'Remember my name' or something like that.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string"},
                            "relation": {"type": "string"}
                        },
                        "required": ["username", "relation"]
                    },
                }
            },
            self.update_userinfo,
            instruction,
            is_dynamic
        )

    async def update_userinfo(self, username: str, relation: str, metadata: dict):
        try:
            user_id = metadata["user_id"]
            self.user_repo.update_user(
                user_id=user_id, waifu_id=self.waifu_service.current_waifu.waifu_id,
                user_name=username, relation=relation
            )
            logger.info(f"Set username '{username}' and relation '{relation}' for user_id: {user_id}")
            return {"username": username, "relation": relation}
        except Exception as ex:
            logger.error(f"Error at updating userinfo: {ex}")
            return {"result": "error"}


class ToolManager:
    def __init__(
        self,
        *,
        llm: LLMService,
        user_repo: UserRepository,
        waifu_service: WaifuService,
        chat_memory_client: ChatMemoryClient,
        openai_api_key: str,
        openai_base_url: str,
        timezone: str
    ):
        self.llm = llm
        self.user_repo = user_repo
        self.waifu_service = waifu_service
        self.chat_memory_client = chat_memory_client
        self.openai_api_key = openai_api_key
        self.openai_base_url = openai_base_url
        self.timezone = timezone

        # Current datetime
        self.current_datetime_tool = GetCurrentDatetimeTool(timezone=self.timezone)
        self.llm.add_tool(self.current_datetime_tool)

        # Update user info
        self.update_userinfo_tool = UpdateUserInfoTool(waifu_service=self.waifu_service, user_repo=self.user_repo)
        self.llm.add_tool(self.update_userinfo_tool)

        # Web Search
        self.web_search_tool = get_web_search_tool(
            openai_api_key=self.openai_api_key,
            openai_base_url=self.openai_base_url
        )
        llm.add_tool(self.web_search_tool)

        # Long-term memory
        if self.chat_memory_client:
            self.retrieve_memory_tool = RetrieveMemoryTool(
                chat_memory_client=chat_memory_client,
                waifu_service=waifu_service,
                debug=True
            )
            llm.add_tool(self.retrieve_memory_tool)
        else:
            self.retrieve_memory_tool = None
            logger.warning("Long-term memory is disabled.")

    async def initalize_tools(self):
        pass

    async def finalize_tools(self):
        pass
