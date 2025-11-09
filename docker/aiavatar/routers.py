import base64
from datetime import datetime, timezone, timedelta
import json
import secrets
from typing import Optional, List
from uuid import uuid4
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from aiavatar.adapter.http.server import AIAvatarHttpServer
from entities import UserRepository, WaifuRepository, ContextRepository, Waifu
from service import WaifuService


class GetContextResponse(BaseModel):
    context_id: Optional[str] = None
    user_id: str
    waifu_id: str

class GetUserResponse(BaseModel):
    user_id: str
    waifu_id: str
    user_name: Optional[str] = None
    relation: Optional[str] = None

class GetWaifuResponse(BaseModel):
    waifu_id: str
    waifu_name: str
    waifu_image: Optional[str] = None
    is_active: bool = False
    speech_service: Optional[str] = None
    speaker: Optional[str] = None
    birthday_mmdd: Optional[str] = None
    metadata: Optional[dict] = None

class WaifuWithoutImage(BaseModel):
    waifu_id: str
    waifu_name: str
    is_active: bool = False
    speech_service: Optional[str] = None
    speaker: Optional[str] = None
    birthday_mmdd: Optional[str] = None
    metadata: Optional[dict] = None

class GetWaifusResponse(BaseModel):
    waifus: List[WaifuWithoutImage]

class PostWaifuRequest(BaseModel):
    waifu_id: str
    waifu_name: Optional[str] = None
    speech_service: Optional[str] = None
    speaker: Optional[str] = None
    birthday_mmdd: Optional[str] = None
    metadata: Optional[dict] = None

class PostWaifuResponse(WaifuWithoutImage):
    pass

class PostWaifuActivateRequest(BaseModel):
    waifu_id: str

class PostWaifuCreateRequest(BaseModel):
    character_name: str
    character_description: str
    speech_service: Optional[str] = None
    speaker: Optional[str] = None
    stream: bool

class PostWaifuCreateResponse(BaseModel):
    waifu_id: str
    waifu_name: str
    is_active: bool = False
    speech_service: Optional[str] = None
    speaker: Optional[str] = None
    character_prompt: str
    weekly_plan_prompt: str
    daily_plan_prompt: str

class PostCliWebBridgeRequest(BaseModel):
    user_id: str

class PostCliWebBridgeResponse(BaseModel):
    link: str


def get_waifu_router(
    http_adapter: AIAvatarHttpServer,
    user_repo: UserRepository,
    waifu_repo: WaifuRepository,
    context_repo: ContextRepository,
    waifu_service: WaifuService
):
    router = APIRouter()
    bearer_scheme = HTTPBearer(auto_error=False)
    cli_web_bridge_tokens = {}

    @router.get("/context", response_model=GetContextResponse)
    async def get_context(
        user_id: str,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):
        if http_adapter.api_key:
            http_adapter.api_key_auth(credentials)

        if not user_id:
            return JSONResponse(content={"error": "user_id is required"}, status_code=400)

        waifu = waifu_service.current_waifu
        if not waifu:
            return JSONResponse(content={"error": "No waifus"}, status_code=404)

        # Get context
        context_info = context_repo.get_context(user_id, waifu.waifu_id)

        return GetContextResponse(
            context_id=context_info.context_id if context_info else None,
            waifu_id=waifu.waifu_id,
            user_id=user_id
        )

    @router.get("/user", response_model=GetUserResponse)
    async def get_user(
        user_id: Optional[str] = None,
        waifu_id: Optional[str] = None,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):
        if http_adapter.api_key:
            http_adapter.api_key_auth(credentials)

        waifu_id = waifu_id or waifu_service.current_waifu.waifu_id

        user = user_repo.get_user(user_id=user_id, waifu_id=waifu_id)
        if not user:
            # Create user if user-waifu pair record doesn't exist
            user = user_repo.update_user(
                user_id=user_id if user_repo.user_exists(user_id=user_id) else f"user_{uuid4()}",
                waifu_id=waifu_id
            )

        return GetUserResponse(
            user_id=user.user_id,
            waifu_id=user.waifu_id,
            user_name=user.user_name,
            relation=user.relation
        )

    @router.get("/waifu/{waifu_id}", response_model=GetWaifuResponse)
    async def get_waifu_by_id(
        waifu_id: str,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):
        if http_adapter.api_key:
            http_adapter.api_key_auth(credentials)

        waifu = waifu_service.waifu_repo.get_waifu(waifu_id=waifu_id)
        if not waifu:
            return JSONResponse(content={"error": f"waifu not found: waifu_id={waifu_id}"}, status_code=404)

        image_b64 = base64.b64encode(waifu_service.image).decode("utf-8")

        return GetWaifuResponse(
            waifu_id=waifu.waifu_id,
            waifu_name=waifu.waifu_name,
            waifu_image=image_b64,
            is_active=waifu.is_active,
            speech_service=waifu.speech_service,
            speaker=waifu.speaker,
            birthday_mmdd=waifu.birthday_mmdd,
            metadata=waifu.metadata
        )

    @router.get("/waifu", response_model=GetWaifuResponse)
    async def get_waifu(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):
        if http_adapter.api_key:
            http_adapter.api_key_auth(credentials)

        waifu = waifu_service.current_waifu
        if not waifu:
            return JSONResponse(content={"error": "waifu is not created yet"}, status_code=404)

        return await get_waifu_by_id(waifu.waifu_id, credentials)

    @router.get("/waifus", response_model=GetWaifusResponse)
    async def get_waifus(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):
        if http_adapter.api_key:
            http_adapter.api_key_auth(credentials)
        
        return GetWaifusResponse(waifus=[WaifuWithoutImage(
            waifu_id=w.waifu_id,
            waifu_name=w.waifu_name,
            is_active=w.is_active,
            speech_service=w.speech_service,
            speaker=w.speaker,
            birthday_mmdd=w.birthday_mmdd,
            metadata=w.metadata
        ) for w in waifu_repo.get_waifus()])

    @router.post("/waifu", response_model=PostWaifuResponse)
    async def post_waifu(
        request: PostWaifuRequest,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):
        if http_adapter.api_key:
            http_adapter.api_key_auth(credentials)

        waifu = waifu_repo.get_waifu(waifu_id=request.waifu_id)
        if not waifu:
            return JSONResponse(content={"error": "waifu is not found"}, status_code=404)

        return await waifu_service.update(
            waifu_id=request.waifu_id,
            waifu_name=request.waifu_name,
            speech_service=request.speech_service,
            speaker=request.speaker,
            birthday_mmdd=request.birthday_mmdd,
            metadata=request.metadata
        )

    @router.post("/waifu/icon")
    async def post_waifu_icon(
        waifu_id: str = Form(...),
        icon: UploadFile = File(...),
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):
        if http_adapter.api_key:
            http_adapter.api_key_auth(credentials)

        waifu = waifu_repo.get_waifu(waifu_id=waifu_id)
        if not waifu:
            return JSONResponse(content={"error": "waifu is not found"}, status_code=404)

        if icon.content_type != "image/png":
            return JSONResponse(content={"error": "icon must be a PNG file"}, status_code=400)

        image_bytes = await icon.read()
        if not image_bytes:
            return JSONResponse(content={"error": "icon file is empty"}, status_code=400)

        waifu_service.update_image(waifu_id=waifu_id, image_bytes=image_bytes)

        return JSONResponse(content={"result": "success"})

    @router.post("/waifu/create")
    async def post_waifu_create(
        request: PostWaifuCreateRequest,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):
        if http_adapter.api_key:
            http_adapter.api_key_auth(credentials)

        async def stream_response():
            async for data, data_type in waifu_service.create(
                character_name=request.character_name,
                character_description=request.character_description,
                speech_service=request.speech_service,
                speaker=request.speaker
            ):
                if data_type != "final":
                    yield json.dumps({"type": data_type, "content": data if isinstance(data, str) else None})
                else:
                    waifu: Waifu = data
                    yield json.dumps({"type": data_type, "content": PostWaifuCreateResponse(
                        waifu_id=waifu.waifu_id,
                        waifu_name=waifu.waifu_name,
                        is_active=waifu.is_active,
                        speech_service=waifu.speech_service,
                        speaker=waifu.speaker,
                        character_prompt=waifu_service.prompt_builder.get_character_prompt(waifu.waifu_id),
                        weekly_plan_prompt=waifu_service.prompt_builder.get_weekly_plan_prompt(waifu.waifu_id),
                        daily_plan_prompt=waifu_service.prompt_builder.get_daily_plan_prompt(waifu.waifu_id)
                    ).model_dump()})

        if request.stream:
            return EventSourceResponse(stream_response())
        else:
            async for r, t in stream_response():
                if t == "final":
                    return r

    @router.post("/waifu/activate")
    async def post_waifu_activate(
        request: PostWaifuActivateRequest,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):
        if http_adapter.api_key:
            http_adapter.api_key_auth(credentials)

        waifu = waifu_repo.get_waifu(waifu_id=request.waifu_id)
        if not waifu:
            return JSONResponse(content={"error": "waifu is not found"}, status_code=404)

        return await waifu_service.activate(request.waifu_id)

    @router.post("/cli-web-bridge/start", response_model=PostCliWebBridgeResponse)
    async def post_cli_web_bridge_start(request: PostCliWebBridgeRequest):
        user_id = request.user_id
        if not user_id or not isinstance(user_id, str):
            return JSONResponse({"error": "user_id required"}, status_code=400)

        code = secrets.token_urlsafe(16)
        cli_web_bridge_tokens[code] = {
            "user_id": user_id,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)
        }
        link = f"/cli-web-bridge/open?code={code}"
        return PostCliWebBridgeResponse(link=link)

    @router.get("/cli-web-bridge/open", response_class=HTMLResponse)
    async def get_cli_web_bridge_open(code: str):
        token = cli_web_bridge_tokens[code]
        now = datetime.now(timezone.utc)
        if not token or token["expires_at"] < now:
            return JSONResponse("Token expired or invalid", status_code=410)
        html = f"""
<!doctype html>
<meta charset="utf-8">
<title>Linking…</title>
<script>
try {{
  localStorage.setItem("userId", "{token['user_id']}");
}} catch (e) {{
  console.error("localStorage write failed", e);
}}
window.location.replace("../../static/index.html");
</script>
<p>Linking… If not redirected, <a href="../../static/index.html">click here</a>.</p>
"""
        return HTMLResponse(html)

    return router
