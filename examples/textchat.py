import json
from uuid import uuid4
import httpx

BASE_URL = "http://127.0.0.1:8012/aiavatar/api"

client = httpx.Client(timeout=30)

# Create new user to start chat instantly
def create_user() -> str:
    resp = client.get(url=BASE_URL + "/user")
    return resp.json()["user_id"]

# Send request and print response
def chat(session_id: str, user_id: str, context_id: str, text: str) -> str:
    with client.stream(
        method="POST",
        url=BASE_URL + "/chat",
        json={
            "type": "start",
            "session_id": session_id,
            "user_id": user_id,
            "context_id": context_id,
            "text": text,
        }
    ) as stream:
        # Process Server-Sent Events stream response
        for chunk in stream.iter_lines():
            if chunk[:5] == "data:":
                chunk_json = json.loads(chunk[5:])
                # The first response. This includes request message.
                if chunk_json["type"] == "start":
                    print("AI: ", end="")
                # Chunk response. Each chunk includes just one sentence.
                elif chunk_json["type"] == "chunk":
                    if voice_text := chunk_json.get("voice_text"):
                        print(voice_text, end="")
                # The final response. This includes whole response sentences.
                elif chunk_json["type"] == "final":
                    print("")
                    # Return context_id to keep converstation context
                    return chunk_json["context_id"]

# Setup ids
session_id = f"sess_{uuid4()}"
user_id = create_user() # Or, set your user_id in `~/.waifucli/default.env`
context_id = None

# Main
while True:
    user_input = input("User: ")
    if not user_input:
        continue
    context_id = chat(session_id, user_id, context_id, user_input)
