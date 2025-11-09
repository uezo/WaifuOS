import json
import threading
import httpx


class WaifuCreator:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def start_wizard(self):
        print("="*40)
        print("\033[1;3mWAIFU CREATOR\033[0m")
        print("="*40)

        character_name = ""
        while True:
            if not character_name:
                character_name = input("Character Name: ").strip()
                if character_name:
                    break

        character_description = ""
        while True:
            prompt = "Character Description" if not character_description else "More Description? (Blank to finish)"
            character_description_line = input(f"{prompt}: ").strip()
            if not character_description_line:
                if character_description:
                    break
            character_description += f"\n- {character_description_line}"

        character_voice_service = input("Character Voice Service (Blank to use default): ").strip()
        character_voice_speaker = input("Character Voice Speaker (Blank to use default): ").strip()

        print("="*40)
        print(f"Character Name: {character_name}")
        print(f"Character Description:{character_description}")
        print(f"Character Voice Service: {character_voice_service}")
        print(f"Character Voice Speaker: {character_voice_speaker}")
        print("")
        while True:
            confirmation = input(f"Are you sure to create '{character_name}'? (y/n): ")
            if confirmation.lower() == "y":
                print("\nCreating your waifu...")
                final_message = ""
                with httpx.stream(
                    method="post",
                    url=self.base_url + "/waifu/create",
                    json={
                        "character_name": character_name,
                        "character_description": character_description,
                        "speech_service": character_voice_service,
                        "speaker": character_voice_speaker,
                        "stream": True
                    },
                    timeout=300.0,
                ) as resp:
                    status_items = [
                        ("character_prompt", "Character Prompt"),
                        ("weekly_plan_prompt", "Weekly Activity Prompt"),
                        ("daily_plan_prompt", "Today's Activity Prompt"),
                        ("image_bytes", "Icon Image"),
                    ]
                    status_progress = {key: False for key, _ in status_items}
                    spinner_frames = "|/-\\"
                    spinner_index = 0
                    print_lock = threading.Lock()
                    stop_spinner = threading.Event()

                    def render_status(initial: bool = False, show_spinner: bool = True) -> None:
                        nonlocal spinner_index
                        with print_lock:
                            if not initial:
                                print(f"\033[{len(status_items)}F", end="")
                            active_key = next(
                                (key for key, _ in status_items if not status_progress[key]),
                                None,
                            )
                            lines = []
                            blank_suffix = "   "
                            for key, label in status_items:
                                mark = "✅" if status_progress[key] else "□"
                                if key == active_key and show_spinner:
                                    suffix = f" {spinner_frames[spinner_index]} "
                                else:
                                    suffix = blank_suffix
                                lines.append(f"{mark} {label}{suffix}")
                            print("\n".join(lines), flush=True)
                            if active_key is not None and show_spinner:
                                spinner_index = (spinner_index + 1) % len(spinner_frames)
                            else:
                                spinner_index = 0

                    def spinner_loop() -> None:
                        while not stop_spinner.is_set():
                            if all(status_progress.values()):
                                stop_spinner.set()
                                break
                            render_status(show_spinner=True)
                            stop_spinner.wait(0.2)

                    render_status(initial=True)
                    spinner_thread = threading.Thread(target=spinner_loop, daemon=True)
                    spinner_thread.start()

                    try:
                        for chunk in resp.iter_lines():
                            if chunk.startswith("data:"):
                                chunk_json = json.loads(chunk[5:].strip())
                                data_type = chunk_json.get("type") or chunk_json.get("data_type")
                                if data_type in status_progress:
                                    if not status_progress[data_type]:
                                        status_progress[data_type] = True
                                        all_done = all(status_progress.values())
                                        render_status(show_spinner=not all_done)
                                        if all_done:
                                            stop_spinner.set()
                                elif data_type == "warning":
                                    final_message += f"⚠️ {chunk_json.get('content')}\n"
                                elif data_type == "final":
                                    final_message += f"\033[1;3m💍 Your waifu '{character_name}' is ready!\033[0m\n\nRun 'waifu' to start chatting with {character_name}."
                                    stop_spinner.set()
                                    break
                                elif data_type == "error":
                                    stop_spinner.set()
                                    final_message += f"💔 {chunk_json.get('content')}"
                                    break
                    finally:
                        stop_spinner.set()
                        spinner_thread.join(timeout=1.0)
                        render_status(show_spinner=False)

                print("="*40)
                print(final_message)
                print("="*40)
                break

            elif confirmation.lower() == "n":
                print("💔 Canceled")
                break
