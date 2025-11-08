from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import os
import re
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from aiavatar import AIAvatarRequest
from aiavatar.adapter.websocket.server import AIAvatarWebSocketServer, WebSocketSessionData
from aiavatar.adapter.http.server import AIAvatarHttpServer
from aiavatar.sts.models import STSRequest, STSResponse
from aiavatar.sts.stt import SpeechRecognizerDummy
from aiavatar.sts.tts import SpeechSynthesizerDummy
from aiavatar.sts.tts.speech_gateway import SpeechGatewaySpeechSynthesizer

from entities import UserRepository, WaifuRepository, ContextRepository, Waifu
from prompt import PromptBuilder
from service import WaifuService
from pipeline import STSPipelineManager
from scheduler import WaifuScheduler
from tools import register_tools, initalize_tools, finalize_tools
from routers import get_waifu_router
from chatmemory import ChatMemoryClient


# -------------------------------------------------------------------
# Configurations and logging
# -------------------------------------------------------------------

# Environment variables
load_dotenv()
AIAVATAR_DEBUG = os.getenv("AIAVATAR_DEBUG", "false").lower() in ("true", "1", "yes")
AIAVATAR_LOG_LEVEL = os.getenv("AIAVATAR_LOG_LEVEL", "INFO")
AIAVATAR_API_KEY=os.getenv("AIAVATAR_API_KEY")
AIAVATAR_DAY_BOUNDARY_TIME=os.getenv("AIAVATAR_DAY_BOUNDARY_TIME")
DATA_DIR = "/data"
OPENAI_API_KEY = os.getenv("LLM_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("LLM_MODEL")
OPENAI_TEMPERATURE = os.getenv("LLM_TEMPERATURE")
OPENAI_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT")
TIMEZONE = os.getenv("TIMEZONE")

# Configure root logger
logger = logging.getLogger()
logger.setLevel(AIAVATAR_LOG_LEVEL)
log_format = logging.Formatter("[%(levelname)s] %(asctime)s : %(message)s")
streamHandler = logging.StreamHandler()
streamHandler.setFormatter(log_format)
logger.addHandler(streamHandler)


# -------------------------------------------------------------------
# Shared components
# -------------------------------------------------------------------

# Shared components
user_repo = UserRepository(connection_str=f"{DATA_DIR}/user.db")
waifu_repo = WaifuRepository(connection_str=f"{DATA_DIR}/waifu.db")
context_repo = ContextRepository(connection_str=f"{DATA_DIR}/context.db")
prompt_builder = PromptBuilder(
    data_dir=DATA_DIR,
    openai_api_key=OPENAI_API_KEY,
    openai_model=OPENAI_MODEL,
    openai_reasoning_effort=OPENAI_REASONING_EFFORT,
    timezone=TIMEZONE
)
waifu_service = WaifuService(
    data_dir=DATA_DIR,
    waifu_repo=waifu_repo,
    user_repo=user_repo,
    prompt_builder=prompt_builder,
    openai_api_key=OPENAI_API_KEY,
    openai_model=OPENAI_MODEL,
    openai_reasoning_effort=OPENAI_REASONING_EFFORT,
    timezone=TIMEZONE
)
sts_manager = STSPipelineManager(waifu_service=waifu_service)
vad, stt, llm, tts, session_state_manager, performance_recorder = sts_manager.get_pipeline_components()
waifu_scheduler = WaifuScheduler(timezone=TIMEZONE, debug=AIAVATAR_DEBUG)
chat_memory_client = ChatMemoryClient(base_url="http://chatmemory:8000")

# Waifu activation
@waifu_service.on_waifu_activated
async def on_waifu_activated(activated_waifu: Waifu):
    # Update shared context
    llm.shared_context_ids = [
        "ctx_global_shared",
        activated_waifu.shared_context_id
    ]
    # Update voice
    if isinstance(tts, SpeechGatewaySpeechSynthesizer):
        tts.service_name = activated_waifu.speech_service
        tts.speaker = activated_waifu.speaker

@waifu_service.on_waifu_updated
async def on_waifu_updated(updated_waifu: Waifu):
    # Update voice
    if isinstance(tts, SpeechGatewaySpeechSynthesizer):
        tts.service_name = updated_waifu.speech_service
        tts.speaker = updated_waifu.speaker


# -------------------------------------------------------------------
# WebSocket and RESTful API Adapter and Speech-to-Speech components
# -------------------------------------------------------------------

# Create WebSocket Adapter
ws_app = AIAvatarWebSocketServer(
    vad=vad,
    stt=stt,
    llm=llm,
    tts=tts,
    merge_request_threshold=3.0,
    session_state_manager=session_state_manager,
    performance_recorder=performance_recorder,
    voice_recorder_dir=f"{DATA_DIR}/recorded_voices",
    debug=AIAVATAR_DEBUG
)

# Create RESTful API server
http_app = AIAvatarHttpServer(
    stt=SpeechRecognizerDummy(),
    llm=llm,
    tts=SpeechSynthesizerDummy(),
    merge_request_threshold=3.0,
    session_state_manager=session_state_manager,
    performance_recorder=performance_recorder,
    voice_recorder_dir=f"{DATA_DIR}/recorded_voices",
    api_key=AIAVATAR_API_KEY,
    debug=True
)

# Tools
register_tools(
    llm=llm,
    user_repo=user_repo,
    waifu_service=waifu_service,
    chat_memory_client=chat_memory_client,
    openai_api_key=OPENAI_API_KEY,
    timezone=TIMEZONE
)

# Start message (for WebSocket only)
@ws_app.on_connect
async def on_connect(request: AIAvatarRequest, session_data: WebSocketSessionData):
    user = user_repo.get_user(request.user_id, waifu_id=waifu_service.current_waifu.waifu_id)
    if not user:
        user = user_repo.update_user(user_id=f"user_{uuid4()}", waifu_id=waifu_service.current_waifu.waifu_id)
    if not user.user_name or not user.relation:
        on_start_request = "$You've suddenly blanked on the user's name and the nature of your relationship with them. Ask the user - sounding a bit flustered - for both pieces of information, and don't continue with any other conversation until they're confirmed."
        async for response in ws_app.sts.invoke(STSRequest(
            session_id=request.session_id,
            user_id=request.user_id,
            context_id=request.context_id,
            text=on_start_request
        )):
            ws_app.sts.vad.set_session_data(request.session_id, "context_id", response.context_id)
            await ws_app.handle_response(response)
    else:
        now_str = datetime.now(ZoneInfo(TIMEZONE)).strftime('%Y/%m/%d %H:%M:%S')
        session_data.data["on_start_prefix"] = f"$You received the following request from the user. Please begin the conversation.\nThe current date and time is {now_str}.\n\n"

@stt.postprocess
async def stt_postprocess(session_id: str, text: str, data: bytes, preprocess_metadata: dict):
    session_data = ws_app.sessions.get(session_id)
    if on_start_prefix := session_data.data.get("on_start_prefix"):
        del session_data.data["on_start_prefix"]
        return on_start_prefix + text
    else:
        return text

# Stop response immediately (for WebSocket only)
async def on_recording_started(session_id: str):
    await ws_app.stop_response(session_id, "")
vad.on_recording_started = on_recording_started

# Multi language
async def process_llm_chunk(chunk: STSResponse):
    match = re.search(r"\[lang:([a-zA-Z-]+)\]", chunk.text)
    if match:
        return {"language": match.group(1)}
    else:
        return {}
ws_app.sts.process_llm_chunk(process_llm_chunk)
http_app.sts.process_llm_chunk(process_llm_chunk)

# Context management and Long-term memory
async def on_finish(request: STSRequest, response: STSResponse):
    # Save context_id by the pair of waifu_id and user_id
    if response.context_id and response.user_id:
        context_repo.update_context(
            context_id=response.context_id,
            user_id=response.user_id,
            waifu_id=waifu_service.current_waifu.waifu_id
        )
    # Save Long-term memory
    try:
        await chat_memory_client.enqueue_messages(request, response, waifu_service.current_waifu.waifu_id)
    except Exception as ex:
        logger.error(f"Error at enqueue memory: {ex}")
ws_app.sts.on_finish(on_finish)
http_app.sts.on_finish(on_finish)


# -------------------------------------------------------------------
# Scheduler
# -------------------------------------------------------------------

@waifu_scheduler.cron("0 3 * * *", id="clear_contexts_job")
def clear_contexts_job():
    context_repo.remove_context()

@waifu_scheduler.cron("0 3 * * *", id="update_daily_plan_job")
async def update_daily_plan_job():
    await waifu_service.prompt_builder.generate_daily_plan_prompt(
        waifu_id=waifu_service.current_waifu.waifu_id,
        character_prompt=waifu_service.character_prompt,
        weekly_plan_prompt=waifu_service.weekly_plan_prompt
    )


# -------------------------------------------------------------------
# FastAPI Server Application
# -------------------------------------------------------------------

# Lifespan
from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app: FastAPI):
    await initalize_tools()
    waifu_scheduler.start()
    yield
    await finalize_tools()
    waifu_scheduler.shutdown()

# Build FastAPI server
app = FastAPI(
    lifespan=lifespan,
    openapi_url="/aiavatar/openapi.json",
    servers=[{"url": "/aiavatar"}]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set adapters
ws_router = ws_app.get_websocket_router(path="/connect")
http_router = http_app.get_api_router(stt=stt, tts=tts)
waifu_router = get_waifu_router(
    http_adapter=http_app,
    user_repo=user_repo,
    waifu_repo=waifu_repo,
    context_repo=context_repo,
    waifu_service=waifu_service
)
app.include_router(ws_router, prefix="/ws")
app.include_router(http_router, prefix="/api", tags=["Conversation"])
app.include_router(waifu_router, prefix="/api", tags=["Waifu management"])
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/waifus", StaticFiles(directory="/data/waifus"), name="waifus")
