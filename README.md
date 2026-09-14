# Discord Auto Quest Completer

**Auto-complete Discord quests without downloading or playing the games.** Discord Auto Quest is a small Python **Discord quest bot / self-bot** that farms `PLAY_ON_DESKTOP` and `WATCH_VIDEO` / `WATCH_VIDEO_ON_MOBILE` quests, auto-accepts them, and shows a **Playing &lt;game&gt;** status on your profile — entirely from the command line, with **no Discord desktop app needed**.

- Keywords: Discord quest completer, Discord quest bot, auto complete Discord quests, Discord quest automation, Discord quest farming, complete Discord quests without installing the game

> [!WARNING]
> Self-bots violate Discord's Terms of Service and automating a user account can get it suspended. This project is for educational purposes only. Use at your own risk.

## Features

- **Auto-completes Discord quests** by sending the same quest heartbeats the official client sends
- Completes `PLAY_ON_DESKTOP` (play a game on desktop for X minutes) quests
- Completes `WATCH_VIDEO` / `WATCH_VIDEO_ON_MOBILE` (watch a video) quests
- Lists all of your current Discord quests so you can pick which ones to complete
- Hides expired and not-yet-started quests, so the list has no dead or duplicate entries
- Auto-accepts pending quests for you, and waits if auto-accept fails
- Shows a **Playing &lt;game&gt;** Rich Presence status through the Discord gateway, then clears it automatically once the quests are done
- Automatic retries for rate limits, server errors, and network failures
- No game installation, no Discord client, no browser extensions, no desktop app — runs entirely from the command line

## Supported quest types

| Quest type | Description | Supported |
| --- | --- | --- |
| `PLAY_ON_DESKTOP` | Play a game on desktop for a set number of minutes | Yes |
| `WATCH_VIDEO` | Watch a video for a set number of seconds | Yes |
| `WATCH_VIDEO_ON_MOBILE` | Watch a video on mobile | Yes |
| `STREAM_ON_DESKTOP` | Stream a game on desktop | No |
| `PLAY_ACTIVITY` | Play a Discord activity | No |

## Requirements

- Python 3.9+
- A Discord user token (self-bot token, not a bot token)

## Install

```sh
git clone https://github.com/SUDIN010/discord-auto-quest.git
cd discord-auto-quest
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
Ignoring 31 expired or not-yet-started quest(s).
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
4. When the quest is done, the script clears your Playing status and exits.
5. Claim the reward in Discord under **Settings → Gift Inventory**.

## How it works

1. `GET /users/@me` verifies the token.
2. `GET /quests/@me` lists your quests and their task configs.
3. Expired and not-yet-started quests are dropped (Discord returns them too, which otherwise causes duplicate-looking entries and `Quest has expired` enroll errors).
4. Pending quests are accepted with `POST /quests/{id}/enroll`.
5. `PLAY_ON_DESKTOP`: `POST /quests/{id}/heartbeat` with the quest's `application_id` every 20 seconds, followed by a final `terminal: true` heartbeat.
6. `WATCH_VIDEO`: `POST /quests/{id}/video-progress` with incrementing timestamps.
7. A websocket connection to the Discord gateway publishes the **Playing** presence, and clears it once every selected quest is finished.

## FAQ

**How do I complete Discord quests without downloading the game?**
Run this Discord quest completer. It replays the same quest heartbeats the official client sends for `PLAY_ON_DESKTOP` quests, and spoofs video progress for `WATCH_VIDEO` quests, so you never install or launch the game.

**Can I auto-complete Discord quests?**
Yes. The script auto-accepts pending quests, tracks progress, and completes them without input. Use `--game "Name"` to target one game automatically, or pick quests interactively.

**Is this a Discord quest bot that works without the desktop app?**
Yes. It talks to the Discord API and gateway directly, so no Discord desktop app, browser extension, or game install is required.

**Do mobile video quests (`WATCH_VIDEO_ON_MOBILE`) work?**
Yes. Mobile video quests are completed through the same video-progress endpoint.

**How long does a quest take?**
Desktop play and video quests are time-gated by Discord's servers, so a 15-minute quest takes about 15 minutes. Video quests finish almost instantly if you accepted them a while ago.

**Why do I see the same game multiple times in the list?**
Discord returns expired and not-yet-started quests too. The script filters those out, so only active quests are shown.

**Where is my reward?**
Rewards are never claimed automatically. Claim them in Discord under **Settings → Gift Inventory**.

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
