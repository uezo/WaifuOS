![WaifuOS — The software suite for creating your waifu and the world where your waifu lives.💕](document/images/waifuos_title.png)

# WaifuOS

The software suite for creating your waifu and the world where your waifu lives.💕


## 💎 Features

- 🎁 **All-in-One:** Everything you need—character AI, speech synthesis, databases, and infrastructure—packed so you can meet your waifu out of the box.
- ⏳ **Lives Her Days:** She lives your day, follows her own schedule, and keeps your shared memories.
- 🎨 **Customizable:** Tailor her personality, look, and voice to your taste.
- 🧩 **One Waifu, Many Channels:** A single waifu connects to web, avatar, and messaging apps through shared context over RESTful APIs or WebSockets.
- 💞 **Multi-Waifu:** Create multiple waifus and switch between them anytime.


## 🚀 Quick Start

Follow the steps below after cloning the repository with `git clone https://github.com/uezo/WaifuOS.git`:

1. Clone this repository

    ```sh
    git clone https://github.com/uezo/WaifuOS.git
    ```

1. Copy .env template file

    ```sh
    cd docker
    cp .env.sample .env
    ```

1. Set OpenAI API key

    ```ini
    # Required
    OPENAI_API_KEY=sk-YOUR-OPENAI-API-KEY

    # Option (STT for WebSocket and TTS for non-Japanese languages)
    AZURE_SPEECH_API_KEY=YOUR_AZURE_SPEECH_SERVICE_API_KEY
    AZURE_SPEECH_REGION=AZURE_SPEECH_SERVICE_REGION
    ```

1. Make initial data

    ```sh
    sh init-data.sh
    ```

1. Start WaifuOS

    ```sh
    docker compose up -d
    ```


## 💍 Create your waifu with CLI

1. Install WaifuOS CLI

    ```sh
    cd cli
    pip install -e .
    ```

2. Start CLI to create waifu

    Start creating waifu.

    ```sh
    waifu create
    ```

    Enter the folloing information about the waifu you want to create:

    - Name: Name of your waifu
    - Description(s): Personality, appearance, memorable episodes, etc. Press Enter to add multiple entries.
    - Voice Service Name: Name of the speech synthesis service. By default, enter one of `voicevox`, `sbv2`, `azure`, or `openai`.
    - Speaker Name: Enter the voice identifier for the chosen speech synthesis service. For VOICEVOX, `2` for Tohoku Metan (Normal).

    Example:

    ```sh
    ========================================
    WAIFU CREATOR
    ========================================
    Character Name: とうか
    Character Description:

    - ユーザーの幼馴染。関心がないように見せかけて、実はいつも気にかけている
    - しっかりもの。物静かな方
    - 銀髪、水色の瞳
    - ふんわりボブ
    Character Voice Service: voicevox
    Character Voice Speaker: 46

    Are you sure to create 'とうか'? (y/n): y

    Creating your waifu...
    ✅ Character Prompt   
    ✅ Weekly Activity Prompt   
    ✅ Today's Activity Prompt   
    ✅ Icon Image   
    ========================================
    💍 Your waifu 'とうか' is ready!

    Run 'waifu' to start chatting with とうか.
    ========================================
    ```

3. Start chatting with your new waifu in terminal

    ```sh
    waifu
    ```

    Your waifu will first ask for your name and how you’re related, so be sure to answer. Every conversation afterward reflects that setting.

    ```sh
    とうか: ごめん、急に飛んじゃって…。Userの名前と、私との関係、もう一度教えて。
    User: うえぞうだよ。幼馴染じゃん
    とうか: [Processing update_userinfo ...]
    [Finish update_userinfo !]
    そっか、うえぞうね。思い出した、ごめん。
    ```

    To start a voice chat in the browser, run `waifu browser` after you set your name and relationship in the CLI.

    NOTE: You can pass the user ID from the CLI to the browser, but sending it the other way requires manually editing the configuration file. The CLI configuration file lives at `~/.waifucli/default.env`.


## 🛠️ Customize

### Character settings

You can customize your waifu by editting files in `{DATA_DIR}/aiavatar/waifus/{waifu_id}`

- Character system prompt: character_prompt.md
- Weekly plan prompt: plan_weekly_prompt.md
- Icon image: icon.png

NOTE: Daily plan is automatically updated every day based on the weekly plan.

### CLI settings

| Environment variable | Type | Default | Description |
| --- | --- | --- | --- |
| `BASE_URL` | string (URL) | `http://127.0.0.1:8012/aiavatar/api` | API endpoint the CLI calls for WaifuOS services. |
| `API_KEY` | string | *(unset)* | API key attached to outbound requests when required by the server. |
| `USER_ID` | string | *(unset)* | Pre-selects the WaifuOS user profile and is reused by the `waifu browser` helper. |
| `ON_START_MESSAGE_PROMPT` | string | *(unset)* | Custom system prompt that is sent once when the session boots. |
| `TIMEZONE` | string (IANA name) | `Asia/Tokyo` | Local timezone used when timestamping or formatting schedule data. |
| `CHARACTER_VOICE_ENABLED` | boolean | `true` | Toggles audio playback for the character voice responses. |
| `FACES` | JSON object | built-in faces | Overrides the ASCII facial expressions mapped by sentiment. |
| `CHARACTER_INTERVAL` | float seconds | `0.02` | Delay between characters when printing messages (typing speed). |
| `ICON_WIDTH_RATIO` | float | `0.5` | Max icon width relative to terminal columns. |
| `ICON_MAX_WIDTH` | integer columns | `40` | Hard cap for icon width in columns. |
| `ICON_MIN_WIDTH` | integer columns | `20` | Minimum icon width to avoid overly small renders. |
| `ICON_ASPECT_RATIO` | float | `1.0` | Aspect ratio clamp applied when scaling icons. |
| `USE_TRUECOLOR` | boolean | `false`* | Forces 24-bit color output; auto-enabled when `COLORTERM=truecolor`. |
| `WAIFU_LABEL_COLOR` | ANSI escape | `\033[38;2;255;64;160m` | ANSI color code for the Waifu speaker label. |
| `USER_LABEL_COLOR` | ANSI escape | `\033[38;2;80;200;120m` | ANSI color code for the user speaker label. |
| `FACE_COLOR` | ANSI escape | `\033[38;2;255;224;243m` | ANSI color code for facial expression text. |
| `TIMEOUT` | float seconds | `60.0` | Request timeout applied to the HTTP client. |
| `OUTPUT_DEVICE_INDEX` | integer | `-1` | Audio output device to select (system dependent). |
| `OUTPUT_CHUNK_SIZE` | integer bytes | `1024` | Size of audio chunks handed to the player. |
| `DEBUG` | boolean | `false` | Enables extra logging and diagnostic output from the CLI. |
| `LOG_LEVEL` | string | `WARNING` | Root logger verbosity for the CLI process. |

*Booleans accept `1`, `true`, `yes`, or `on` (case-insensitive) as truthy values.


## 🧩 API Reference

**WaifuOS** provides a **streaming API** similar to OpenAI’s — supporting **Server-Sent Events (SSE)** for seamless **STT → LLM → TTS** cascades — and a **realtime WebSocket API** for **speech-to-speech** interactions.

These APIs allow you to connect **any frontend or communication channel** — from web apps to custom clients — to your waifu’s intelligence.

We’re preparing **detailed documentation, practical examples**, and **integration guides** for connecting with:

- [**ChatdollKit**](https://github.com/uezo/ChatdollKit), the 3D avatar framework for real-time voice interaction
- **LINE Bot**, for conversational experiences on mobile

Together, these make it easy to build **voice-interactive, emotionally responsive avatars** powered by WaifuOS.

The API specifications conform to **AIAvatarKit** — please refer to the following for details:

- **RESTful API:** [https://github.com/uezo/aiavatarkit?tab=readme-ov-file#-restful-api-sse](https://github.com/uezo/aiavatarkit?tab=readme-ov-file#-restful-api-sse)
- **WebSocket API:** [https://github.com/uezo/aiavatarkit?tab=readme-ov-file#-websocket](https://github.com/uezo/aiavatarkit?tab=readme-ov-file#-websocket)

You can also view and test the API documentation at:
👉 [http://localhost:8012/aiavatar/docs](http://localhost:8012/aiavatar/docs)

> **NOTE:**
> WaifuOS’s RESTful API does **not** include audio data in responses from the `/api/chat` endpoint.
> To generate audio, use the `voice_text` field from each response chunk and send it to the `/api/synthesize` endpoint for speech synthesis.


## ⚖️ License
This project is licensed under the Apache License 2.0 — see the [LICENSE](./LICENSE) file for details.
