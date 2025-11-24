import os
from fastapi import FastAPI
from dotenv import load_dotenv
from chatmemory import ChatMemory

load_dotenv()
CM_DEBUG = os.getenv("CM_DEBUG", "false").lower() in ("true", "1", "yes")
CM_LOG_LEVEL = os.getenv("CM_LOG_LEVEL", "INFO")
# Database
CM_DB_HOST = "db"
CM_DB_PORT = 5432
CM_DB_NAME = os.getenv("CM_DB_NAME")
CM_DB_USER = os.getenv("CM_DB_USER")
CM_DB_PASSWORD = os.getenv("CM_DB_PASSWORD")
# ChatMemory
CM_OPENAI_API_KEY = os.getenv("CM_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
CM_OPENAI_BASE_URL = os.getenv("CM_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL")
CM_LLM_MODEL = os.getenv("CM_LLM_MODEL")
CM_EMBEDDING_MODEL = os.getenv("CM_EMBEDDING_MODEL")

cm = ChatMemory(
    openai_api_key=CM_OPENAI_API_KEY,
    openai_base_url=CM_OPENAI_BASE_URL,
    llm_model=CM_LLM_MODEL,
    embedding_model=CM_EMBEDDING_MODEL,
    db_name=CM_DB_NAME,
    db_user=CM_DB_USER,
    db_password=CM_DB_PASSWORD,
    db_host=CM_DB_HOST,
    db_port=CM_DB_PORT,
)

app = FastAPI(
    title="ChatMemory",
    openapi_url="/chatmemory/openapi.json",
    servers=[{"url": "/chatmemory"}],
    version="0.2.2"
)
app.include_router(cm.get_router())
