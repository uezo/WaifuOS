import logging
import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from sbv2apilite.tts import StyleBertVits2TTS
from sbv2apilite.api import get_api_router

def str_to_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "y", "yes")

SBV2_DEBUG = str_to_bool(os.getenv("SBV2_DEBUG", "false"))
SBV2_LOG_LEVEL = os.getenv("SBV2_LOG_LEVEL", "INFO").upper()
SBV2_USE_GPU = str_to_bool(os.getenv("SBV2_USE_GPU", "false"))
SBV2_FFMPEG_PATH = os.getenv("SBV2_FFMPEG_PATH", "ffmpeg")
SBV2_MP3_BITRATE = os.getenv("SBV2_MP3_BITRATE", "64k")

# Configure root logger
logger = logging.getLogger("sbv2-api-lite")
logger.setLevel(SBV2_LOG_LEVEL)
log_format = logging.Formatter("[%(levelname)s] %(asctime)s : %(message)s")
streamHandler = logging.StreamHandler()
streamHandler.setFormatter(log_format)
logger.addHandler(streamHandler)

# Create Style-Bert-VITS2 API
sbv2tts = StyleBertVits2TTS(
    use_gpu=SBV2_USE_GPU,
    verbose=SBV2_DEBUG,
)

# Create API app
app = FastAPI(
    title="Style-Bert-VITS2 API Lite",
    openapi_url="/sbv2-api-lite/openapi.json",
    servers=[{"url": "/sbv2-api-lite"}]
)
router = get_api_router(sbv2tts, SBV2_MP3_BITRATE, SBV2_FFMPEG_PATH)
app.include_router(router)
