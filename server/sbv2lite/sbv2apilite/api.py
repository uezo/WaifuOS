import logging
from typing import Optional
from style_bert_vits2.constants import Languages
from style_bert_vits2.constants import (
    DEFAULT_ASSIST_TEXT_WEIGHT,
    DEFAULT_LENGTH,
    DEFAULT_LINE_SPLIT,
    DEFAULT_NOISE,
    DEFAULT_NOISEW,
    DEFAULT_SDP_RATIO,
    DEFAULT_SPLIT_INTERVAL,
    DEFAULT_STYLE,
    DEFAULT_STYLE_WEIGHT,
    Languages,
)
from fastapi import APIRouter, Query, File, UploadFile
from fastapi.responses import Response, JSONResponse
from .tts import StyleBertVits2TTS, MP3ConvertProcessor


# Get logger
logger = logging.getLogger(__name__)


def get_api_router(sbv2tts: StyleBertVits2TTS, mp3bitrate: str = "64k", ffmpeg_path: str = "ffmpeg"):
    router = APIRouter()
    mp3_converter_processor = MP3ConvertProcessor(mp3bitrate, ffmpeg_path)

    @router.get("/voice", tags=["Text-to-Speech"])
    async def get_voice(
        text: str = Query(..., alias="text"),
        speaker_id: int = Query(0, alias="speaker_id"),
        sdp_ratio: float = Query(DEFAULT_SDP_RATIO, alias="sdp_ratio"),
        noise: float = Query(DEFAULT_NOISE, alias="noise"),
        noise_w: float = Query(DEFAULT_NOISEW, alias="noisew"),
        length: float = Query(DEFAULT_LENGTH, alias="length"),
        language: Languages = Query(Languages.JP, alias="language"),
        line_split: bool = Query(DEFAULT_LINE_SPLIT, alias="auto_split"),
        split_interval: float = Query(DEFAULT_SPLIT_INTERVAL, alias="split_interval"),
        assist_text: Optional[str] = Query(None, alias="assist_text"),
        assist_text_weight: float = Query(DEFAULT_ASSIST_TEXT_WEIGHT, alias="assist_text_weight"),
        style: str = Query(DEFAULT_STYLE, alias="style"),
        style_weight: float = Query(DEFAULT_STYLE_WEIGHT, alias="style_weight"),
        reference_audio_path: Optional[str] = Query(None, alias="reference_audio_path"),
        x_audio_format: str = Query("wave", alias="x_audio_format")
    ):
        try:
            if sbv2tts.tts_model:
                if x_audio_format == "mp3" and mp3_converter_processor is not None:
                    media_type = "audio/mpeg"
                    post_processor = mp3_converter_processor
                else:
                    media_type = "audio/wav"
                    post_processor = None

                audio_data = await sbv2tts.tts(
                    text=text,
                    speaker_id=speaker_id,
                    style=style,
                    language=language,
                    sdp_ratio=sdp_ratio,
                    noise=noise,
                    noise_w=noise_w,
                    length=length,
                    line_split=line_split,
                    split_interval=split_interval,
                    assist_text=assist_text,
                    assist_text_weight=assist_text_weight,
                    style_weight=style_weight,
                    reference_audio_path=reference_audio_path,
                    post_processor=post_processor
                )
                return Response(content=audio_data, media_type=media_type)

            else:
                return JSONResponse(content={"error": "Text-to-speech model is not loaded."}, status_code=500)

        except Exception as ex:
            logger.error(f"Error in voice generation: {str(ex)}")
            raise ex


    @router.get("/models/info", tags=["Models"])
    async def get_models_info():
        if sbv2tts.tts_model is not None:
            result = {
                "config_path": sbv2tts.tts_model.config_path,
                "model_path": sbv2tts.tts_model.model_path,
                "device": sbv2tts.tts_model.device,
                "spk2id": sbv2tts.tts_model.spk2id,
                "id2spk": sbv2tts.tts_model.id2spk,
                "style2id": sbv2tts.tts_model.style2id
            }
            return JSONResponse(content={"0": result})
    
        else:
            return JSONResponse(content={"error": "Text-to-speech model is not loaded."}, status_code=500)


    @router.put("/models/load", tags=["Models"])
    async def put_models_load(
        model_file: UploadFile = File(...),
        config_file: UploadFile = File(...),
        style_file: UploadFile = File(...),
        use_gpu: bool = False
    ):
        # Save uploaded model
        for file_obj, path in zip(
            [model_file, config_file, style_file],
            [sbv2tts.model_file, sbv2tts.config_file, sbv2tts.style_file]
        ):
            contents = await file_obj.read()
            with open(path, "wb") as f:
                f.write(contents)

        # Load model
        is_loaded = sbv2tts.load_tts_model(use_gpu=use_gpu)

        return JSONResponse(content={"result": "success" if is_loaded else "fail"})

    @router.post("/config/verbose", tags=["Configuration"])
    async def post_config_verbose(
        verbose: bool
    ):
        sbv2tts.verbose = verbose
        return JSONResponse(content={"result": "on" if verbose else "off"})

    return router
