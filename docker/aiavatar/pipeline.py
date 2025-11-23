import logging
import os
from dotenv import load_dotenv
from aiavatar.sts.llm.context_manager.postgres import PostgreSQLContextManager
from aiavatar.sts.session_state_manager.postgres import PostgreSQLSessionStateManager
from aiavatar.sts.performance_recorder.postgres import PostgreSQLPerformanceRecorder
from service import WaifuService

logger = logging.getLogger(__name__)


# Environment variables
load_dotenv()
AIAVATAR_DEBUG = os.getenv("AIAVATAR_DEBUG", "false").lower() in ("true", "1", "yes")

VAD_SILENCE_DURATION_THRESHOLD = float(os.getenv("VAD_SILENCE_DURATION_THRESHOLD", "0.7"))

STT_SERVICE = os.getenv("STT_SERVICE")
STT_LANGUAGE = os.getenv("STT_LANGUAGE")
STT_OPENAI_API_KEY = os.getenv("STT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
STT_AZURE_API_KEY = os.getenv("STT_AZURE_API_KEY") or os.getenv("AZURE_SPEECH_API_KEY")
STT_AZURE_REGION = os.getenv("STT_AZURE_REGION") or os.getenv("AZURE_SPEECH_REGION")

LLM_SERVICE = os.getenv("LLM_SERVICE")
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT")
LLM_OPENAI_API_KEY = os.getenv("LLM_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
LLM_OPENAI_BASE_URL = os.getenv("LLM_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL")

EVAL_LLM_SERVICE = os.getenv("EVAL_LLM_SERVICE")
EVAL_LLM_MODEL = os.getenv("EVAL_LLM_MODEL")
EVAL_LLM_TEMPERATURE = float(os.getenv("EVAL_LLM_TEMPERATURE", "0.0"))
EVAL_LLM_OPENAI_API_KEY = os.getenv("EVAL_LLM_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
EVAL_LLM_OPENAI_BASE_URL = os.getenv("EVAL_LLM_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL")

TTS_SPEECH_GATEWAY = os.getenv("TTS_SPEECH_GATEWAY", "")
TTS_SPEECH_GATEWAY_URL = os.getenv("TTS_SPEECH_GATEWAY_URL")
TTS_SPEECH_GATEWAY_SERVICE_NAME = os.getenv("TTS_SPEECH_GATEWAY_SERVICE_NAME")
TTS_SPEECH_GATEWAY_SPEAKER = os.getenv("TTS_SPEECH_GATEWAY_SPEAKER")

AIAVATAR_DB_HOST = "db"
AIAVATAR_DB_PORT = 5432
AIAVATAR_DB_NAME = os.getenv("AIAVATAR_DB_NAME")
AIAVATAR_DB_USER = os.getenv("AIAVATAR_DB_USER")
AIAVATAR_DB_PASSWORD = os.getenv("AIAVATAR_DB_PASSWORD")
DATABASE_URL = f"postgresql://{AIAVATAR_DB_USER}:{AIAVATAR_DB_PASSWORD}@{AIAVATAR_DB_HOST}:{AIAVATAR_DB_PORT}/{AIAVATAR_DB_NAME}"

AIAVATAR_CONTEXT_TIMEOUT = int(os.getenv("AIAVATAR_CONTEXT_TIMEOUT", 86400))
AIAVATAR_COT_ANSWER = os.getenv("AIAVATAR_COT_ANSWER")


class STSPipelineManager:
    def __init__(self, waifu_service: WaifuService):
        self.waifu_service = waifu_service

    def get_pipeline_components(self):
        # Context Manager
        self.context_manager = PostgreSQLContextManager(connection_str=DATABASE_URL, context_timeout=AIAVATAR_CONTEXT_TIMEOUT)
        # Session State Manager
        self.session_state_manager = PostgreSQLSessionStateManager(connection_str=DATABASE_URL)
        # Performance Recorder
        self.performance_recorder = PostgreSQLPerformanceRecorder(connection_str=DATABASE_URL)

        # -------------------------------------------------------------------
        # VAD
        # -------------------------------------------------------------------
        from aiavatar.sts.vad.silero import SileroSpeechDetector
        self.vad = SileroSpeechDetector(silence_duration_threshold=VAD_SILENCE_DURATION_THRESHOLD, debug=AIAVATAR_DEBUG)

        # -------------------------------------------------------------------
        # STT
        # -------------------------------------------------------------------
        if STT_SERVICE == "openai":
            from aiavatar.sts.stt.openai import OpenAISpeechRecognizer
            self.stt = OpenAISpeechRecognizer(
                openai_api_key=STT_OPENAI_API_KEY,
                debug=AIAVATAR_DEBUG
            )
        elif STT_SERVICE == "azure":
            from aiavatar.sts.stt.azure import AzureSpeechRecognizer
            self.stt = AzureSpeechRecognizer(
                azure_api_key=STT_AZURE_API_KEY,
                azure_region=STT_AZURE_REGION,
                debug=AIAVATAR_DEBUG
            )
        else:
            from aiavatar.sts.stt import SpeechRecognizerDummy
            self.stt = SpeechRecognizerDummy()

        # -------------------------------------------------------------------
        # LLM
        # -------------------------------------------------------------------
        if LLM_SERVICE == "openai":
            from aiavatar.sts.llm.chatgpt import ChatGPTService
            self.llm = ChatGPTService(
                openai_api_key=LLM_OPENAI_API_KEY,
                base_url=LLM_OPENAI_BASE_URL,
                system_prompt="You are the waifu of the user.",
                model=LLM_MODEL,
                temperature=LLM_TEMPERATURE,
                reasoning_effort=LLM_REASONING_EFFORT,
                context_manager=self.context_manager,
                debug=AIAVATAR_DEBUG
            )

        self.llm.split_chars = ["。", "？", "！", "?", "!"]
        self.llm.get_system_prompt = self.waifu_service.get_system_prompt

        # Chain of Thought
        if AIAVATAR_COT_ANSWER:
            self.llm.voice_text_tag = AIAVATAR_COT_ANSWER

        # -------------------------------------------------------------------
        # TTS
        # -------------------------------------------------------------------
        if TTS_SPEECH_GATEWAY.lower() == "true":
            from aiavatar.sts.tts.speech_gateway import SpeechGatewaySpeechSynthesizer
            self.tts = SpeechGatewaySpeechSynthesizer(
                service_name="",
                speaker="",
                tts_url=TTS_SPEECH_GATEWAY_URL,
                audio_format="wav",
                debug=AIAVATAR_DEBUG
            )
        else:
            from aiavatar.sts.tts import SpeechSynthesizerDummy
            self.tts = SpeechSynthesizerDummy()


        # -------------------------------------------------------------------
        # Evaluator
        # -------------------------------------------------------------------

        # Context Manager for Evaluation (In-Memory)
        from aiavatar.sts.llm.context_manager import SQLiteContextManager
        eval_context_manager = SQLiteContextManager(db_path=":memory:")

        # Make evaluator
        from aiavatar.eval.dialog import DialogEvaluator
        eval_llm = ChatGPTService(
            openai_api_key=EVAL_LLM_OPENAI_API_KEY,
            base_url=EVAL_LLM_OPENAI_BASE_URL,
            model=EVAL_LLM_MODEL,
            context_manager=eval_context_manager
        )
        self.evaluator = DialogEvaluator(llm=self.llm, evaluation_llm=eval_llm)

        return self.vad, self.stt, self.llm, self.tts, self.session_state_manager, self.performance_recorder
