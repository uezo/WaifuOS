from datetime import datetime
from zoneinfo import ZoneInfo
from logging import getLogger
from typing import Callable
from urllib.parse import urlparse, parse_qs
import openai
from aiavatar.sts.llm import LLMService, Tool
from entities import UserRepository
from service import WaifuService
from chatmemory import ChatMemoryClient

logger = getLogger(__name__)


def register_tools(
    llm: LLMService,
    *,
    user_repo: UserRepository,
    waifu_service: WaifuService,
    chat_memory_client: ChatMemoryClient,
    openai_api_key: str,
    openai_base_url: str,
    timezone: str
):
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

    current_datetime_tool = GetCurrentDatetimeTool(timezone=timezone)
    llm.add_tool(current_datetime_tool)

    class UpdateUserInfoTool(Tool):
        def __init__(
            self,
            *,
            user_repo: UserRepository,
            name: str = None,
            spec: str = None,
            instruction: str = None,
            is_dynamic: bool = False,
            debug: bool = False
        ):
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

        # 

        async def update_userinfo(self, username: str, relation: str, metadata: dict):
            try:
                user_id = metadata["user_id"]
                self.user_repo.update_user(
                    user_id=user_id, waifu_id=waifu_service.current_waifu.waifu_id,
                    user_name=username, relation=relation
                )
                logger.info(f"Set username '{username}' and relation '{relation}' for user_id: {user_id}")
                return {"username": username, "relation": relation}
            except Exception as ex:
                logger.error(f"Error at updating userinfo: {ex}")
                return {"result": "error"}

    update_userinfo_tool = UpdateUserInfoTool(user_repo=user_repo)
    llm.add_tool(update_userinfo_tool)


    class OpenAIWebSearch:
        def __init__(self,
            *,
            openai_api_key: str,
            system_prompt: str = None,
            base_url: str = None,
            model: str = "gpt-5-search-api",
            temperature: float = 0.5,
            search_context_size: str = "medium",
            country: str = None,
            language: str = None,
            make_query: Callable[[str], str] = None,
            timeout: int = 30000,
            debug: bool = False
        ):
            if "azure" in model:
                api_version = parse_qs(urlparse(base_url).query).get("api-version", [None])[0]
                self.openai_client = openai.AsyncAzureOpenAI(
                    api_key=openai_api_key,
                    api_version=api_version,
                    base_url=base_url,
                    timeout=timeout
                )
            else:
                self.openai_client = openai.AsyncClient(api_key=openai_api_key, base_url=base_url, timeout=timeout)

            self.system_prompt = system_prompt or "Search the web to answer the user's query. Base your response strictly on the search results, and do not include your own opinions."
            self.model = model
            self.temperature = temperature
            self.search_context_size = search_context_size
            self.country = country
            self.language = language
            self.make_query = make_query
            self.debug = debug

        async def search(self, query: str):
            web_search_options = {
                "search_context_size": self.search_context_size
            }
            if self.country:
                web_search_options["user_location"] = {
                    "type": "approximate",
                    "approximate": {
                        "country": self.country
                    }
                }

            if self.make_query:
                query = self.make_query(query)

            if self.debug:
                logger.info(f"OpenAI WebSearch Query: {query}")

            response = await self.openai_client.chat.completions.create(
                model=self.model,
                web_search_options=web_search_options,
                messages=[
                    {"role": "system", "content": self.system_prompt + f"\nOutput language code: {self.language}" if self.language else ""},
                    {"role": "user", "content": f"Search: {query}"}
                ],
            )

            search_result = response.choices[0].message.content
            if self.debug:
                logger.info(f"OpenAI WebSearch Result: {search_result}")

            return {"search_result": search_result}


    class OpenAIWebSearchTool(Tool):
        def __init__(
            self,
            *,
            openai_api_key: str,
            system_prompt: str = None,
            base_url: str = None,
            model: str = "gpt-4o-search-preview",
            temperature: float = 0.5,
            search_context_size: str = "medium",
            country: str = "JP",
            language: str = None,
            make_query: Callable[[str], str] = None,
            timeout: int = 30000,
            name=None,
            spec=None,
            instruction = None,
            is_dynamic = False,
            debug: bool = False
        ):
            self.openai_web_search = OpenAIWebSearch(
                openai_api_key=openai_api_key,
                system_prompt=system_prompt,
                base_url=base_url,
                model=model,
                temperature=temperature,
                search_context_size=search_context_size,
                country=country,
                language=language,
                make_query = make_query,
                timeout=timeout,
                debug=debug
            )
            super().__init__(
                name or "web_search",
                spec or {
                    "type": "function",
                    "function": {
                        "name": name or "web_search",
                        "description": "Search the web using OpenAI WebSearch",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"}
                            },
                            "required": ["query"]
                        },
                    }
                },
                self.openai_web_search.search,
                instruction,
                is_dynamic
            )

    openai_websearch_tool = OpenAIWebSearchTool(openai_api_key=openai_api_key, base_url=openai_base_url)
    llm.add_tool(openai_websearch_tool)

    # Long-term memory
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
                                "query": {"type": "string"}
                            },
                            "required": ["query"]
                        },
                    }
                },
                self.search_memory,
                instruction,
                is_dynamic
            )

        async def search_memory(self, query: str, metadata: dict = None):
            logger.info(f"Search memory: {query}")
            result = await self.chat_memory_client.search(
                user_id=metadata["user_id"],
                waifu_id=waifu_service.current_waifu.waifu_id,
                query=query
            )
            logger.info(f"Search memory result: {result.__dict__}")
            return result.__dict__

    retrieve_memory_tool = RetrieveMemoryTool(
        chat_memory_client=chat_memory_client,
        waifu_service=waifu_service,
        debug=True
    )
    llm.add_tool(retrieve_memory_tool)

async def initalize_tools():
    pass

async def finalize_tools():
    pass
