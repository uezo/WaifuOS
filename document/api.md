# WaifuOS REST API Documentation

This document explains the WaifuOS REST API. Every endpoint is located at the server's base URL with `/aiavatar/api` appended (for example, `http://localhost:8012/aiavatar/api`). Unless otherwise noted, both requests and responses use JSON.

## Basic Information
- **Base Path**: `/aiavatar/api`
- **Authentication**: HTTP Bearer (`Authorization: Bearer <API_KEY>`). Not required if the API key is disabled on the server.
- **Common Headers**: `Content-Type: application/json` (file uploads use `multipart/form-data`), streaming responses use `text/event-stream`.

## Streaming Responses
`/chat` and `waifu/create` (when `stream=true`) return Server-Sent Events (SSE). Both endpoints send one JSON string per line with the `data:` prefix as shown below.

```json
data: {"type":"chunk","voice_text":"...", ...}
```

Clients should inspect the `type` field as each event arrives. The stream is delivered as `text/event-stream` and ends when the HTTP connection closes.

## Conversation API

### POST `/aiavatar/api/chat`
Send user input and receive the response via SSE. Speech-to-Speech (STS) flows that include audio input (`audio_data`) are also supported.

#### Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string | Yes | Type of the user request. Always set to `"start"`. |
| `session_id` | string | Yes | Conversation session ID. Generate a unique value on the client and reuse it throughout the dialogue. |
| `user_id` | string | Yes | User ID. Use the ID returned by GET `/user`. |
| `context_id` | string | No | Conversation context ID for continuity. Send the value returned in the `final` response to maintain context. |
| `text` | string | No | User utterance text. Optional when sending audio input. |
| `audio_data` | string (base64) | No | Base64-encoded audio input (for example, 16 kHz PCM). |
| `files` | array<object> | No | Auxiliary files. Each object contains arbitrary string key/value pairs. |
| `system_prompt_params` | object | No | Additional parameters that override placeholders in the system prompt. |
| `metadata` | object | No | Client-defined metadata that server applications can read and use. |

#### Example Request
```
POST /aiavatar/api/chat HTTP/1.1
Authorization: Bearer <API_KEY>
Content-Type: application/json

{
  "type": "start",
  "session_id": "sess_123456",
  "user_id": "user_abc",
  "context_id": null,
  "text": "Hello! What's on today's schedule?"
}
```

#### Response (SSE)
All events are JSON objects compatible with `AIAvatarResponse`.

| Field | Type | Description |
| --- | --- | --- |
| `type` | string | Response type. For example: `start`, `chunk`, `tool_call`, `final`, `vision`, `error`, `stop`. |
| `session_id` | string | The session ID you provided. |
| `user_id` | string | The user ID you provided. |
| `context_id` | string | Updated conversation context ID. Use the value from the `final` event in subsequent requests. |
| `text` | string | Raw text from the LLM. |
| `voice_text` | string | Text fragments suitable for display or speech synthesis. `chunk` events arrive sentence by sentence (not character by character; punctuation defines each TTS-ready unit). |
| `language` | string | Language code detected for `chunk` events (for example, `ja-JP`). |
| `audio_data` | string (base64) | Audio that has already been synthesized for `chunk` events. |
| `avatar_control_request` | object | Facial expression and animation instructions containing `face_name` / `animation_name` and duration. |
| `metadata` | object | Additional information. `tool_call` events include tool details in `metadata.tool_call`. |

Typical event flow:

```
data: {"type":"start","session_id":"sess_123456","context_id":null}
data: {"type":"chunk","voice_text":"Good morning.","language":"ja","audio_data":"...","avatar_control_request":{"face_name":"smile"}}
data: {"type":"chunk","voice_text":"Let me share today's schedule with you."}
data: {"type":"final","context_id":"ctx_7890","text":"... (combined response)"}
```

- `tool_call`: Progress of a tool execution. Check `metadata.tool_call.name` and `result`.
- `vision`: If the response contains `[vision:<ID>]`, the final event type becomes `vision` and `metadata.source` holds the image identifier.
- `error`: Server-side error. `text` may include details.
- `stop`: Indicates that the server stopped generating the response.

Refer to `examples/textchat.py` for a sample client implementation.

### POST `/aiavatar/api/transcribe`
Upload an audio file and receive its transcription. Speaker identification results are returned when available.

#### Form Data
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `audio` | file | Yes | Audio file (binary). |
| `session_id` | string | No | Session ID. When provided, the STT pipeline (including preprocess/postprocess) can reuse context. |

#### Response
```json
{
  "text": "こんにちは",
  "preprocess_metadata": {...},
  "postprocess_metadata": {...},
  "speakers": {
    "chosen": {"speaker_id": "spk_1", "similarity": 0.87, "metadata": {...}, "is_new": false},
    "candidates": [
      {"speaker_id": "spk_1", "similarity": 0.87, "metadata": {...}, "is_new": false},
      {"speaker_id": "spk_2", "similarity": 0.53, "metadata": {...}, "is_new": true}
    ]
  }
}
```

- `speakers` is returned only when the speaker registry is enabled.
- Returns 401 for authentication errors or 400 if no audio is provided.

### POST `/aiavatar/api/transcribe/speaker`

**NOTE**: Speaker recognition is currently disabled in WaifuOS. The feature exists in AIAvatarKit and may be enabled in the future.

Register a name in the speaker registry. When speaker identification is disabled, an empty object is returned.

#### Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `speaker_id` | string | Yes | Registered speaker ID. |
| `name` | string | Yes | Display name. |

#### Response
```json
{ "speaker_id": "spk_1", "name": "Alice" }
```

### POST `/aiavatar/api/synthesize`
Synthesize speech from text and return it as `audio/wav`.

#### Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `text` | string | Yes | Text to synthesize. |
| `style_info` | object | No | Additional parameters for the synthesis style. |
| `language` | string | No | Speech language code. |

#### Response
- On status 200, the body is a WAV binary (`Content-Type: audio/wav`).
- The response includes `Content-Disposition: attachment; filename=voice.wav`.
- Sending an empty string results in 400.

## Waifu Management API

### GET `/aiavatar/api/context`
Retrieve the current conversation context ID and associated waifu for a given user.

| Query | Type | Required | Description |
| --- | --- | --- | --- |
| `user_id` | string | Yes | Target user ID. |

#### Response
```json
{ "context_id": "ctx_123", "user_id": "user_abc", "waifu_id": "waifu_xyz" }
```

- Returns 404 with `{"error": "No waifus"}` when the target waifu does not exist.

### GET `/aiavatar/api/user`
Fetch user information. When `user_id` is omitted, a new user is created.

| Query | Type | Required | Description |
| --- | --- | --- | --- |
| `user_id` | string | No | User ID. Generated when omitted. |
| `waifu_id` | string | No | Waifu ID to associate with the user. Defaults to the currently active waifu. |

#### Response
```json
{
  "user_id": "user_abc",
  "waifu_id": "waifu_xyz",
  "user_name": "Taro",
  "relation": "friend"
}
```


### GET `/aiavatar/api/waifu/{waifu_id}`
Retrieve details for the specified waifu. The image is returned as a base64-encoded string.

| Path | Type | Required | Description |
| --- | --- | --- | --- |
| `waifu_id` | string | Yes | Waifu ID. |

#### Response
```json
{
  "waifu_id": "waifu_xyz",
  "waifu_name": "Mika",
  "waifu_image": "<base64 PNG>",
  "is_active": true,
  "speech_service": "voicevox",
  "speaker": "46"
}
```

- Returns 404 with `{"error": "waifu not found: waifu_id=..."}` when the waifu does not exist.

### GET `/aiavatar/api/waifu`
Return details of the currently active waifu. Internally identical to `/waifu/{waifu_id}`. Returns 404 with `{"error": "waifu is not created yet"}` if no waifu has been created.

### GET `/aiavatar/api/waifus`
Return a list of registered waifus. Images are omitted.

#### Response
```json
{
  "waifus": [
    {"waifu_id": "waifu_a", "waifu_name": "Mika", "is_active": true, "speech_service": null, "speaker": null},
    {"waifu_id": "waifu_b", "waifu_name": "Yui", "is_active": false, "speech_service": "voicevox", "speaker": "3"}
  ]
}
```

### POST `/aiavatar/api/waifu/create`
Create a new waifu. By default the endpoint returns a single non-streaming response, but setting `stream` to `true` enables SSE progress updates.

#### Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `character_name` | string | Yes | Character name. |
| `character_description` | string | Yes | Character description. |
| `speech_service` | string | No | Identifier of the speech synthesis service. |
| `speaker` | string | No | Speaker ID used for synthesis. |
| `stream` | boolean | Yes | Whether to stream progress. `true` enables SSE, `false` returns only the final result. |

#### Response
- **`stream=false`**: JSON containing the final result

```json
{
  "waifu_id": "waifu_xyz",
  "waifu_name": "isuzu",    // Supports multibyte characters as well
  "is_active": true,
  "speech_service": "voicevox",
  "speaker": "46",
  "character_prompt": "...",
  "weekly_plan_prompt": "...",
  "daily_plan_prompt": "..."
}
```

- **`stream=true`**: SSE (`data: {"type": "...", "content": ...}`) sends the following events in order, ending with `type: "final"`.

| type | content | Description |
| --- | --- | --- |
| `character_prompt` | string | Generated character prompt. |
| `weekly_plan_prompt` | string | Weekly plan prompt. |
| `daily_plan_prompt` | string | Daily plan prompt. |
| `image_bytes` | `null` | Sent when an image is generated. In the current implementation the content is not encoded, so `null` is returned. |
| `error` | string | Error message encountered during generation. |
| `final` | object | Final result with the same structure as the JSON above. |


### POST `/aiavatar/api/waifu/activate`
Activate an existing waifu.

#### Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `waifu_id` | string | Yes | Waifu ID to activate. |

#### Response
`Waifu` object:
```json
{
  "waifu_id": "waifu_xyz",
  "waifu_name": "Mika",
  "is_active": true,
  "speech_service": "voicevox",
  "speaker": "46",
  "shared_context_id": "ctx_shared"
}
```

- Returns 404 with `{"error": "waifu is not found"}` if the ID does not exist.


### POST `/aiavatar/api/cli-web-bridge/start`
Generate a temporary link that connects the CLI client with the browser.

#### Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `user_id` | string | Yes | User ID to bridge. |

#### Response
```json
{ "link": "/cli-web-bridge/open?code=xxxx" }
```

- Returns 400 with `{"error": "user_id required"}` when `user_id` is missing.
- The link is valid for five minutes after issuance.

### GET `/aiavatar/api/cli-web-bridge/open`
Receive the code obtained from `/cli-web-bridge/start`, store `userId` in the browser's `localStorage`, and return HTML that redirects to `/static/index.html`.

| Query | Type | Required | Description |
| --- | --- | --- | --- |
| `code` | string | Yes | Token issued by `/cli-web-bridge/start`. |

- Returns 410 when the code is expired or invalid.
- Successful responses use `text/html`.

## Authentication and Security Notes
- Always send a Bearer token for every endpoint when an API key is configured; missing or invalid keys return 401 (`{"detail": "Invalid or missing API Key"}`).
- SSE endpoints keep the connection open for a long time, so configure client timeouts accordingly.
- File uploads and synthesized audio responses can be large. Implement client-side timeouts and retry logic.
