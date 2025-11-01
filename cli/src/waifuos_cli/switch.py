import httpx

class WaifuSwitcher:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def list_waifus(self):
        resp = httpx.get(
            url=self.base_url + "/waifus",
            timeout=10.0,
        )
        resp.raise_for_status()
        waifus = resp.json()
        i = 1
        for w in waifus:
            print(f"{i}. {w['name']}")

    def switch_waifu(self, waifu_id: str = None):
        if not waifu_id:
            # List waifus
            resp = httpx.get(
                url=self.base_url + "/waifus",
                timeout=10.0,
            )
            resp.raise_for_status()
            waifus = resp.json()["waifus"]
            i = 0
            for w in waifus:
                i += 1
                print(f"{i}. {w['waifu_name']}{' 💍' if w['is_active'] else ''}")
            # Select waifu
            while True:
                user_input = input("Select index: ").strip()
                try:
                    idx = int(user_input)
                    waifu_id = waifus[idx - 1]['waifu_id']
                    break
                except Exception as ex:
                    print(ex)
                if not waifu_id:
                    continue

        activate_resp = httpx.post(
            url=self.base_url + "/waifu/activate",
            json={
                "waifu_id": waifu_id
            },
            timeout=60.0,
        )
        activate_resp.raise_for_status()
        print(f"\033[1;3m💍 Successfully switched to '{activate_resp.json()['waifu_name']}'!\033[0m")
