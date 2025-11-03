# WaifuOS　CLI

With WaifuCLI, you can text-chat with your Waifu (with the Waifu side speaking) and create new Waifus through the WaifuOS RESTful API.

## 📚 Usage

### Chat with Waifu

To start chatting with your Waifu, simply run `waifu`.

```sh
waifu
```

### Create new waifu

To create a new Waifu, run `waifu create`.

```sh
waifu create
```

Example:

```sh
$ waifu create
========================================
WAIFU CREATOR
========================================
Character Name: いすず
Character Description: 三毛猫タイプの招き猫の化身の美少女
More Description? (Blank to finish): 見た目は16歳くらいだが実年齢は数百年以上
More Description? (Blank to finish): 基本的に語尾は「じゃ」だが、興奮すると猫っぽく「にゃ」の語尾が混ざる
More Description? (Blank to finish): 普段は気分屋でおっちょこちょいにも見えるが、本質的には聡明で誠実
More Description? (Blank to finish): 
Character Voice Service (Blank to use default): voicevox
Character Voice Speaker (Blank to use default): 46
========================================
Character Name: いすず
Character Description:
- 三毛猫タイプの招き猫の化身の美少女
- 見た目は16歳くらいだが実年齢は数百年以上
- 基本的に語尾は「じゃ」だが、興奮すると猫っぽく「にゃ」の語尾が混ざる
- 普段は気分屋でおっちょこちょいにも見えるが、本質的には聡明で誠実
Character Voice Service: voicevox
Character Voice Speaker: 46

Are you sure to create 'いすず'? (y/n): y

Creating your waifu...
✅ Character Prompt   
✅ Weekly Activity Prompt   
✅ Today's Activity Prompt   
✅ Icon Image   
========================================
💍 Your waifu 'いすず' is ready!

Run 'waifu' to start chatting with いすず.
========================================
```


### Switch waifu

To switch the active Waifu, run `waifu switch` and choose the Waifu you want to activate.

```sh
waifu switch
```

Example:

```sh
$ waifu switch
1. みうな 💍
2. さゆ
3. いすず
Select index: 3

💍 Successfully switched to 'いすず'!
```


### Make alias to waifu command

By creating an alias, you can launch the `waifu` command under a different command name.

```sh
waifu alias [alias_name]
```

Example:

```sh
$ waifu alias isuzu
Alias 'isuzu' created at /Users/username/dev/WaifuOS/.venv/bin/isuzu

$ isuzu
(chat starts with your Waifu)
```


## 🛠️ Configuration

The WaifuOS CLI reads the following environment variables. If you set them in `~/.waifucli/default.env`, they’re loaded automatically at startup. Creating `~/.waifucli/{alias name}.env` lets you override the defaults whenever you launch the CLI via that alias.

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
