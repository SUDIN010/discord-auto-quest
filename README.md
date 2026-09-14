# Discord Quest Completer

A small Python self-bot that completes Discord quests without downloading the games, and keeps a **Playing &lt;game&gt;** status on your profile.

Made for the common quest types:

- **Play a game on desktop for X minutes** (`PLAY_ON_DESKTOP`)
- **Watch a video** (`WATCH_VIDEO`, `WATCH_VIDEO_ON_MOBILE`)

> [!WARNING]
> Self-bots violate Discord's Terms of Service and automating a user account can get it suspended. This project is for educational purposes only. Use at your own risk.

## Features

- Completes `PLAY_ON_DESKTOP` quests by sending the same quest heartbeats the official client sends
- Completes `WATCH_VIDEO` / `WATCH_VIDEO_ON_MOBILE` quests
- Lists all current quests so you can pick which ones to complete
- Auto-accepts pending quests, and waits for you if auto-accept fails
- Shows a **Playing &lt;game&gt;** Rich Presence status through the Discord gateway
- Automatic retries for rate limits, server errors, and network failures
- No game installation, no Discord client, no browser extensions

## Requirements

- Python 3.9+
- A Discord user token

## Install

```sh
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Usage

Create a `.env` file from the example and put your token in it:

```sh
cp .env.example .env      # Windows: copy .env.example .env
```

```env
DISCORD_TOKEN=your_token_here
```

Then just run:

```sh
python main.py
```

You can also set the `DISCORD_TOKEN` environment variable instead of using `.env`:

```sh
# Windows (PowerShell)
$env:DISCORD_TOKEN = "YOUR_TOKEN"; python main.py

# Linux / macOS
DISCORD_TOKEN="YOUR_TOKEN" python main.py
```

Options:

| Flag | Default | Description |
| --- | --- | --- |
| `--game` | none | Complete every quest matching this game name instead of prompting |
| `--status` | `online` | Presence: `online`, `idle`, `dnd`, or `invisible` |
| `-v`, `--verbose` | off | Debug logging |

By default the script lists all of your current quests and asks which to complete:

```text
Available quests:
  [1] Play Marvel Rivals (PLAY_ON_DESKTOP) - not accepted
  [2] Watch a video (WATCH_VIDEO) - accepted
Select quests (numbers like 1,3 or 'all'):
```

To skip the prompt and target a specific game:

```sh
python main.py --game "Fortnite" --status dnd
```

## How to use it

1. Open Discord, go to **Quests**, and either accept the quest or let the script try to accept it for you.
2. Run the script and keep it open for the full quest duration (usually 15 minutes).
3. The console prints progress (`Quest progress: 120s/900s (13 min left)`).
4. Claim the reward in Discord under **Settings → Gift Inventory**.

## How it works

1. `GET /users/@me` verifies the token.
2. `GET /quests/@me` lists your quests and their task configs.
3. Pending quests are accepted with `POST /quests/{id}/enroll`.
4. `PLAY_ON_DESKTOP`: `POST /quests/{id}/heartbeat` with the quest's `application_id` every 20 seconds, followed by a final `terminal: true` heartbeat.
5. `WATCH_VIDEO`: `POST /quests/{id}/video-progress` with incrementing timestamps.
6. A websocket connection to the Discord gateway publishes the **Playing** presence.

## Limitations

- Discord's quest UI does not update live for third-party clients — refresh Discord to see progress.
- Rewards are never claimed automatically; claiming can require a captcha.
- `STREAM_ON_DESKTOP` and `PLAY_ACTIVITY` quests are not supported.
- When several quests match, they are completed one after another (desktop play first, then video).

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Login failed: ... 401` | The token is wrong or expired. Never share it. |
| `No '<game>' quests found` | The quest expired, or `--game` does not match the game name. Run with `--verbose` and check the logged quest names. |
| Quest is not progressing | Refresh Discord and make sure the quest is accepted. Progress updates on Discord's side every heartbeat. |
| Auto-accept failed | Accept the quest manually in Discord; the script keeps running and starts as soon as it is accepted. |
| `Rate limited, retrying in ...` | Normal; the script backs off and retries automatically. |

## Security

Never commit your token. Keep it in `.env` (already ignored by git) or in the `DISCORD_TOKEN` environment variable. If a token ever leaks, reset it immediately in Discord settings.

## Disclaimer

This project is not affiliated with, endorsed by, or connected to Discord Inc. It exists purely for educational purposes. Using it may violate Discord's Terms of Service and can result in account restrictions. The author is not responsible for any consequences of using this software.
