import argparse
import asyncio
import base64
import json
import logging
import os
import random
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import requests
import websockets
from dotenv import load_dotenv

API = "https://discord.com/api/v10"
GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"

HEARTBEAT_SECONDS = 20
VIDEO_TICK_SECONDS = 1
VIDEO_SPEED = 7
VIDEO_MAX_FUTURE = 10
MAX_RETRIES = 5
REQUEST_TIMEOUT = 30

TASK_PRIORITY = ("PLAY_ON_DESKTOP", "WATCH_VIDEO", "WATCH_VIDEO_ON_MOBILE")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) discord/1.0.9215 Chrome/138.0.7204.251 "
    "Electron/37.6.0 Safari/537.36"
)

log = logging.getLogger("quest-completer")


class QuestError(RuntimeError):
    pass


def build_super_properties() -> str:
    properties = {
        "os": "Windows",
        "browser": "Discord Client",
        "release_channel": "stable",
        "client_version": "1.0.9215",
        "os_version": "10.0.19045",
        "os_arch": "x64",
        "app_arch": "x64",
        "system_locale": "en-US",
        "has_client_mods": False,
        "client_launch_id": str(uuid.uuid4()),
        "browser_user_agent": USER_AGENT,
        "browser_version": "37.6.0",
        "os_sdk_version": "19045",
        "client_build_number": 471091,
        "native_build_number": 72186,
        "client_event_source": None,
    }
    return base64.b64encode(json.dumps(properties).encode()).decode()


def build_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "X-Super-Properties": build_super_properties(),
        "X-Discord-Locale": "en-US",
        "Origin": "https://discord.com",
        "Referer": "https://discord.com/channels/@me",
    }


class QuestClient:
    def __init__(self, token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(build_headers(token))

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(method, f"{API}{path}", timeout=REQUEST_TIMEOUT, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(2**attempt)
                continue

            if response.status_code == 429:
                retry_after = 5.0
                try:
                    retry_after = float(response.json().get("retry_after", retry_after))
                except (ValueError, AttributeError):
                    pass
                log.warning("Rate limited, retrying in %.1fs", retry_after)
                time.sleep(retry_after + 1)
                continue

            if response.status_code >= 500:
                last_error = QuestError(f"{method} {path} -> {response.status_code}")
                time.sleep(2**attempt)
                continue

            if not response.ok:
                raise QuestError(f"{method} {path} -> {response.status_code}: {response.text[:300]}")

            if not response.content:
                return {}
            try:
                return response.json()
            except ValueError:
                return {}

        raise QuestError(f"{method} {path} failed after {MAX_RETRIES} attempts: {last_error}")

    def me(self) -> Dict[str, Any]:
        return self.request("GET", "/users/@me")

    def quests(self) -> List[Dict[str, Any]]:
        return self.request("GET", "/quests/@me").get("quests", [])

    def enroll(self, quest_id: str, quest: Dict[str, Any]) -> Dict[str, Any]:
        body: Dict[str, Any] = {"location": 11, "is_targeted": False, "metadata_raw": None}
        for key in ("traffic_metadata_raw", "traffic_metadata_sealed"):
            if quest.get(key) is not None:
                body[key] = quest[key]
        status = self.request("POST", f"/quests/{quest_id}/enroll", json=body)
        return status.get("user_status", status)

    def game_heartbeat(self, quest_id: str, application_id: str, terminal: bool) -> Dict[str, Any]:
        status = self.request(
            "POST",
            f"/quests/{quest_id}/heartbeat",
            json={"application_id": application_id, "terminal": terminal},
        )
        return status.get("user_status", status)

    def video_progress(self, quest_id: str, timestamp: float) -> Dict[str, Any]:
        status = self.request("POST", f"/quests/{quest_id}/video-progress", json={"timestamp": timestamp})
        return status.get("user_status", status)


def quest_tasks(quest: Dict[str, Any]) -> Dict[str, Any]:
    config = quest.get("config") or {}
    task_config = config.get("task_config_v2") or config.get("task_config") or {}
    return task_config.get("tasks") or {}


def quest_app_id(quest: Dict[str, Any]) -> Optional[str]:
    task = quest_tasks(quest).get("PLAY_ON_DESKTOP") or {}
    for application in task.get("applications") or []:
        if application.get("id"):
            return application["id"]
    return ((quest.get("config") or {}).get("application") or {}).get("id")


def quest_name(quest: Dict[str, Any]) -> str:
    return (quest.get("config") or {}).get("messages", {}).get("quest_name") or quest.get("id", "unknown quest")


def quest_state(quest: Dict[str, Any]) -> str:
    if completed(quest):
        return "completed"
    return "accepted" if enrolled(quest) else "not accepted"


def enrolled(quest: Dict[str, Any]) -> bool:
    return bool((quest.get("user_status") or {}).get("enrolled_at"))


def completed(quest: Dict[str, Any]) -> bool:
    return bool((quest.get("user_status") or {}).get("completed_at"))


def task_progress(status: Optional[Dict[str, Any]], task_name: str) -> int:
    progress = (status or {}).get("progress") or {}
    return int((progress.get(task_name) or {}).get("value") or 0)


def parse_time(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def matches_game(quest: Dict[str, Any], game: str) -> bool:
    config = quest.get("config") or {}
    messages = config.get("messages") or {}
    application = config.get("application") or {}
    text = " ".join(
        str(part)
        for part in (
            application.get("name"),
            messages.get("quest_name"),
            messages.get("game_title"),
        )
        if part
    )
    return game.lower() in text.lower()


def task_priority(quest: Dict[str, Any]) -> int:
    tasks = quest_tasks(quest)
    for index, name in enumerate(TASK_PRIORITY):
        if name in tasks:
            return index
    return len(TASK_PRIORITY)


async def call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(func, *args, **kwargs)


async def presence_worker(token: str, activity: Dict[str, Any], status: str) -> None:
    while True:
        try:
            async with websockets.connect(GATEWAY_URL, max_size=None) as socket:
                hello = json.loads(await socket.recv())
                interval = hello["d"]["heartbeat_interval"] / 1000

                async def heartbeat() -> None:
                    while True:
                        await asyncio.sleep(interval)
                        await socket.send(json.dumps({"op": 1, "d": None}))

                heartbeat_task = asyncio.create_task(heartbeat())
                try:
                    await socket.send(
                        json.dumps(
                            {
                                "op": 2,
                                "d": {
                                    "token": token,
                                    "properties": {
                                        "$os": "Windows",
                                        "$browser": "Discord Client",
                                        "$device": "Discord Client",
                                    },
                                    "presence": {
                                        "status": status,
                                        "afk": False,
                                        "activities": [activity],
                                    },
                                },
                            }
                        )
                    )
                    log.info("Playing status set to '%s'", activity["name"])
                    async for raw in socket:
                        data = json.loads(raw)
                        if data.get("op") == 7:
                            break
                finally:
                    heartbeat_task.cancel()
        except Exception as exc:
            log.debug("Gateway disconnected: %s", exc)
        await asyncio.sleep(5)


async def wait_for_enrollment(client: QuestClient, quest_id: str) -> Dict[str, Any]:
    while True:
        for quest in await call(client.quests):
            if quest.get("id") == quest_id and enrolled(quest):
                return quest
        log.info("Waiting for you to accept the quest in Discord...")
        await asyncio.sleep(10)


async def complete_play_on_desktop(client: QuestClient, quest: Dict[str, Any]) -> None:
    tasks = quest_tasks(quest)
    task = tasks.get("PLAY_ON_DESKTOP")
    if not task:
        return

    target = int(task.get("target") or 900)
    app_id = quest_app_id(quest)
    if not app_id:
        log.error("No application id found for '%s'", quest_name(quest))
        return

    log.info("Simulating %s for quest progress (%.0f min needed). Keep this running.", quest_name(quest), target / 60)
    finished = False

    while True:
        status = await call(client.game_heartbeat, quest["id"], app_id, False)
        progress = task_progress(status, "PLAY_ON_DESKTOP")
        if status.get("completed_at") or progress >= target:
            finished = True
            break
        if not status.get("progress"):
            log.warning("Unexpected heartbeat response: %s", json.dumps(status)[:300])
            break
        log.info("Quest progress: %ds/%ds (%.0f min left)", progress, target, max(0, target - progress) / 60)
        await asyncio.sleep(HEARTBEAT_SECONDS)

    final = await call(client.game_heartbeat, quest["id"], app_id, True)
    if finished or final.get("completed_at"):
        log.info("Quest completed: %s", quest_name(quest))
        log.info("Claim the reward in Discord: Settings > Gift Inventory")
    else:
        log.warning("Stopped before completion: %s", quest_name(quest))


async def complete_watch_video(client: QuestClient, quest: Dict[str, Any]) -> None:
    tasks = quest_tasks(quest)
    task_name = next(name for name in ("WATCH_VIDEO", "WATCH_VIDEO_ON_MOBILE") if name in tasks)
    target = int(tasks[task_name].get("target") or 60)

    status = quest.get("user_status") or {}
    progress = task_progress(status, task_name)
    enrolled_at = parse_time(status.get("enrolled_at"))
    if not enrolled_at:
        log.error("Quest is not accepted: %s", quest_name(quest))
        return

    log.info("Spoofing video for '%s' (%ds needed).", quest_name(quest), target)
    finished = progress >= target

    while not finished:
        max_allowed = int(time.time() - enrolled_at) + VIDEO_MAX_FUTURE
        timestamp = progress + VIDEO_SPEED
        if max_allowed - progress >= VIDEO_SPEED:
            result = await call(client.video_progress, quest["id"], min(target, timestamp + random.random()))
            if result.get("completed_at"):
                finished = True
                break
            progress = min(target, timestamp)
            log.info("Video progress: %ds/%ds", progress, target)
        if timestamp >= target:
            break
        await asyncio.sleep(VIDEO_TICK_SECONDS)

    if not finished:
        result = await call(client.video_progress, quest["id"], target)
        finished = bool(result.get("completed_at"))

    if finished:
        log.info("Quest completed: %s", quest_name(quest))
        log.info("Claim the reward in Discord: Settings > Gift Inventory")
    else:
        log.warning("Video progress sent, but quest is not marked complete yet: %s", quest_name(quest))


async def complete_quest(client: QuestClient, quest: Dict[str, Any]) -> None:
    tasks = quest_tasks(quest)
    if "PLAY_ON_DESKTOP" in tasks:
        await complete_play_on_desktop(client, quest)
    elif "WATCH_VIDEO" in tasks or "WATCH_VIDEO_ON_MOBILE" in tasks:
        await complete_watch_video(client, quest)
    else:
        log.warning("Unsupported quest type (%s): %s", ", ".join(tasks) or "unknown", quest_name(quest))


async def run(args: argparse.Namespace) -> int:
    load_dotenv()
    token = (os.getenv("DISCORD_TOKEN") or "").strip()
    if not token:
        log.error("No token found. Put DISCORD_TOKEN in .env or set it as an environment variable.")
        return 1

    client = QuestClient(token)
    try:
        user = await call(client.me)
    except QuestError as exc:
        log.error("Login failed: %s", exc)
        return 1
    log.info("Logged in as %s (%s)", user["username"], user["id"])

    quests: List[Dict[str, Any]] = []
    try:
        quests = await call(client.quests)
    except QuestError as exc:
        log.error("Could not fetch quests: %s", exc)

    matches = sorted((quest for quest in quests if matches_game(quest, args.game)), key=task_priority)

    activity: Dict[str, Any] = {"name": args.game, "type": 0}
    if matches:
        for quest in matches:
            log.info("Found quest: %s [%s] (%s)", quest_name(quest), ", ".join(quest_tasks(quest)), quest_state(quest))
        app_id = quest_app_id(matches[0])
        if app_id:
            activity["application_id"] = app_id
    else:
        log.warning("No '%s' quests found.", args.game)

    asyncio.create_task(presence_worker(token, activity, args.status))

    pending = [quest for quest in matches if not completed(quest)]
    for quest in pending:
        if enrolled(quest):
            continue
        try:
            quest["user_status"] = await call(client.enroll, quest["id"], quest)
            log.info("Accepted quest: %s", quest_name(quest))
        except QuestError as exc:
            log.warning("Could not auto-accept '%s': %s", quest_name(quest), exc)

    for quest in sorted(pending, key=lambda quest: not enrolled(quest)):
        if not enrolled(quest):
            quest = await wait_for_enrollment(client, quest["id"])
        try:
            await complete_quest(client, quest)
        except QuestError as exc:
            log.error("Quest completion error: %s", exc)

    await asyncio.Event().wait()
    return 0


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="discord-quest-completer",
        description="Complete Discord quests and show a Playing status without installing the game.",
    )
    parser.add_argument("--game", default="Marvel Rivals", help="Game name whose quests to complete (default: %(default)s)")
    parser.add_argument(
        "--status",
        default="online",
        choices=("online", "idle", "dnd", "invisible"),
        help="Presence status to show (default: %(default)s)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
