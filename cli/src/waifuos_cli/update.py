import httpx

class WaifuUpdater:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def update_waifu(self, waifu_id: str = None):
        if waifu_id:
            resp = httpx.get(
                url=self.base_url + "/waifus",
                timeout=10.0,
            )
            resp.raise_for_status()
            waifus = resp.json()["waifus"]
            for w in waifus:
                if w["waifu_id"] == waifu_id:
                    waifu = w
                    break
        else:
            resp = httpx.get(
                url=self.base_url + "/waifu",
                timeout=10.0,
            )
            resp.raise_for_status()
            waifu = resp.json()

        payload = {
            "waifu_id": waifu["waifu_id"]
        }
        if waifu_name := input(f"Name({waifu['waifu_name']}): "):
            payload["waifu_name"] = waifu_name
        if speech_service := input(f"Voice Service({waifu['speech_service']}): "):
            payload["speech_service"] = speech_service
        if speaker := input(f"Voice Speaker({waifu['speaker']}): "):
            payload["speaker"] = speaker
        if birthday_mmdd := input(f"Birthday({waifu['birthday_mmdd']}): "):
            payload["birthday_mmdd"] = birthday_mmdd

        update_resp = httpx.post(
            url=self.base_url + "/waifu",
            json=payload,
            timeout=60.0,
        )
        update_resp.raise_for_status()
        print(f"\033[1;3m Successfully updated '{update_resp.json()['waifu_name']}'!\033[0m")
