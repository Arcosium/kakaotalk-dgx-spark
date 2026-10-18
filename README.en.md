# KakaoTalk on DGX Spark

**Run the official Windows KakaoTalk client on ARM64 Linux, then let Claude Code or Codex operate it through a desktop MCP.**

Hangover + FEX runs the app. An isolated Xvfb desktop keeps it separate from your regular desktop. noVNC lets you log in from a browser; the bundled `/카카오톡` skill asks for your approval before sending messages or files.

[한국어 안내](README.md)

## What works

| Operation | Observed on the original DGX Spark environment |
| --- | --- |
| Official client launch and QR login | Confirmed |
| Read visible chats | Confirmed |
| Paste Korean messages and send after approval | Confirmed |
| Download a received DOCX to a Linux project folder | Confirmed; ZIP integrity checked |
| Local Korean/English OCR for text-only agents | Confirmed |
| One-time local credential registration and fallback login | Confirmed on 2026-10-18; friends list verified |
| Local conversation skill discovery and MCP connection | Confirmed on the original Hermes local-chat profile |
| Browser access through noVNC | Confirmed |
| Open the file attachment chooser and browse Linux folders | Confirmed |
| Send a server file attachment | Confirmed in My Chat with a 74-byte text file, after user approval |

On 2026-10-12, a server-side `kakao-attachment-test.txt` was sent to **My Chat**. The test followed explicit user approval, opened the file chooser, selected the Linux file through Wine's `Z:` mapping, confirmed the separate **Send 1 files** dialog, and verified the resulting file bubble with the matching filename, 74-byte size and send time. This confirms a small text-file upload in the original working environment; a fresh remote download of that sent file, larger files and other attachment types were not checked in this test. No account names or chat screenshots are included here.

The original working environment used Ubuntu 24.04.4 ARM64, 4 KB pages, Hangover 11.16 with FEX, and KakaoTalk 26.8.2.5324. This repository packages that implementation for other users. **The new setup script has not yet been exercised on a fresh machine.** Other ARM machines and later client versions may behave differently.

## Architecture

```text
Claude Code / Codex / compatible local agent
                  │ stdio MCP
                  ▼
          dedicated Xvfb desktop
          official KakaoTalk client
             Hangover + FEX
                  │
       x11vnc ← noVNC browser login
```

This uses the app's visible UI, rather than a chat-history API. Mobile history is available only to the extent it syncs to the PC client. Opening a room can mark messages read.

## Install

Target: **Ubuntu 24.04 ARM64 / DGX Spark**, Python 3.12. Install system dependencies first:

```bash
sudo apt update
sudo apt install python3-venv python3-pip git xvfb xauth openbox \
  x11vnc xdotool xclip tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng \
  wine64 fonts-noto-cjk
git clone https://github.com/Arcosium/kakaotalk-dgx-spark.git
cd kakaotalk-dgx-spark
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python setup.py --install-app
```

The system Wine package supplies runtime dependencies. The app runs with the separate Hangover runtime downloaded from its upstream release. The script checks the pinned Hangover archive's SHA-256, pins the noVNC revision, installs Korean fonts and OCR data, and fetches KakaoTalk's installer from the official CDN. Complete the installer in the browser, then run:

```bash
.venv/bin/python manage.py start
```

The KakaoTalk client, Hangover, noVNC and font binaries are downloaded from their respective upstreams, not redistributed in this repository.

## Log in from your browser

On the server, open **http://127.0.0.1:6086/vnc.html**. From another computer, first forward the port:

```bash
ssh -L 6086:127.0.0.1:6086 USER@SERVER
```

Open the same localhost address on that computer. The screen password is generated separately from your Linux/sudo password. Read it in your own server terminal:

```bash
cat ~/.local/share/kakaotalk-dgx-spark/vnc-password.txt
```

### First-time account authentication

Keep the account you intend to use signed in on your phone. You are authenticating the PC client running on this server, not registering a Kakao Developers app.

1. In the noVNC KakaoTalk login screen, click **QR Code Log In**.
2. On your phone, open KakaoTalk **More → the QR scan icon at the upper right**. This route comes from the verified PC client's QR login instructions; the mobile layout can vary.
3. Scan the QR shown in your noVNC browser, check that the login request is yours, and approve it on your phone.
4. If a first-time PC verification or additional authentication screen appears, follow the phone and PC app prompts yourself. Enter any requested verification code directly into the designated field; do not share it with the agent.
5. When the PC chat list appears in noVNC, login is complete. You can then ask the agent to read a specific room.

If the QR expires, refresh it in the PC app and scan again. A server-local PNG link may not appear in the chat interface; use the actual noVNC browser screen. You can also enter account credentials directly in the PC client or register them locally as described below. Follow additional authentication prompts yourself. Preserve the existing Wine prefix for subsequent sessions.

### Register once for fallback login

Run in your server terminal; both account and password input are hidden:

```bash
.venv/bin/python credentials.py set
.venv/bin/python credentials.py status
```

Credentials are stored in `login.json` under the data directory, outside the checkout by default, with mode 600. This is a plaintext file protected by your server account's filesystem permissions. Never place account values in agent prompts, source code, MCP arguments, logs or GitHub. The login helper reads them only after recognizing a logged-out login form, then clears the shared clipboard. An already authenticated session does not read credentials.

The skill calls `ensure_logged_in` before a task. After a successful fallback login, inspect and reselect the recipient and input. `type_text` also checks the session and returns `typed: false` instead of entering text after a fallback or an unrecognized screen. Failed login and additional authentication stop without automatic retry. Complete authentication through noVNC yourself, or register corrected credentials with `credentials.py set`. `credentials.py forget` removes stored values without logging the app out. `.venv/bin/python auth.py` runs the same session check without MCP.

The VNC and web endpoints bind only to localhost. Account data, screenshots, downloaded runtimes and authentication files live under `~/.local/share/kakaotalk-dgx-spark/`, outside the checkout. Override this with `KAKAOTALK_DATA_DIR`; set the same value in your MCP environment. `KAKAOTALK_DISPLAY` selects a display instead of the default `:119`. Ports remain 5906 and 6086, so this implementation supports one instance per host.

## Connect Claude Code and Codex

Run these commands **inside this checkout**:

```bash
# Shared /카카오톡 skill for both agents
.venv/bin/python install_skill.py both

# Codex MCP
codex mcp add kakao-desktop -- "$PWD/.venv/bin/python" "$PWD/mcp_server.py"

# Claude Code MCP, available to your user
claude mcp add --scope user --transport stdio kakao-desktop \
  -- "$PWD/.venv/bin/python" "$PWD/mcp_server.py"
```

The installer writes the skill to `~/.codex/skills/카카오톡/` and `~/.claude/skills/카카오톡/`, using the paths to this checkout and interpreter. It refuses to replace an existing skill by default. Use `install_skill.py both --update` to back up the current copies under the data directory's `skill-backups/` before updating. Source-managed symlinks are preserved. Keep the checkout in place after installing, and start a new agent session to discover the skill and MCP server.

### Local conversations (Hermes local-chat)

```bash
.venv/bin/python install_skill.py local
# To update a previously installed local skill:
.venv/bin/python install_skill.py local --update
```

The local skill uses `$HERMES_HOME/skills` or `~/.hermes/local-chat/skills`. `install_skill.py all` includes Claude Code, Codex and local conversations. Register the server in your local agent's `config.yaml` and add `skills` and `kakao-desktop` to the existing `platform_toolsets.cli` list. Explicitly listing another MCP server can restrict the enabled servers to that list: registration alone does not expose KakaoTalk tools to the model. The following is a minimal example; retain your other existing toolsets. Replace the absolute paths. If you use `KAKAOTALK_DATA_DIR`, set the same value in the server's `env`.

```yaml
platform_toolsets:
  cli: [web, file, skills, kakao-desktop]
mcp_servers:
  kakao-desktop:
    command: /absolute/path/kakaotalk-dgx-spark/.venv/bin/python
    args:
      - /absolute/path/kakaotalk-dgx-spark/mcp_server.py
```

Start a new local conversation process and load the `카카오톡` skill; existing processes may retain the previous tool list. Custom chat/work mode plugins must retain `skills` and `kakao-desktop` in chat mode too. Text-only agents use `read_screen`; ambiguous recipients or text require inspection before proceeding. The same explicit approval is required for every message or file transmission.

Other MCP clients can use the same stdio configuration:

```json
{
  "mcpServers": {
    "kakao-desktop": {
      "command": "/absolute/path/kakaotalk-dgx-spark/.venv/bin/python",
      "args": ["/absolute/path/kakaotalk-dgx-spark/mcp_server.py"]
    }
  }
}
```

Example requests:

```text
/카카오톡 Read the latest messages in the room I specify.
/카카오톡 Prepare a reply, show me the exact text, and ask before sending.
/카카오톡 Download the newest DOCX in that room to my project folder.
/카카오톡 Attach /absolute/path/document.pdf to that room, after my approval.
```

The workflow shows the recipient and exact text or file details, waits for explicit approval, performs the send once, and checks the outgoing bubble. An initial "send this" request does not skip that approval. This is an **agent workflow requirement**, not an enforced access-control boundary: the MCP exposes general desktop actions. Use one trusted agent at a time.

## Tools

| Tool | Action |
| --- | --- |
| `start_desktop` | Start/reconnect the dedicated desktop |
| `ensure_logged_in` | Check session; log in once from a verified form using local credentials |
| `show_chats` | Open the verified chat list and return room/preview/timestamp OCR coordinates |
| `screen` | Current PNG without retaining a screenshot |
| `read_screen` | Local Korean/English OCR with coordinates |
| `click`, `move_mouse` | Click or hover verified screen coordinates |
| `press` | Key combinations; Enter can send |
| `type_text` | Session check, then Unicode clipboard paste without Enter |
| `scroll` | Scroll the hovered area |

For text-only agents, `show_chats` avoids guessing the sidebar icon coordinates from OCR. It finds the current main window, matches the chat-tab silhouette in a fresh screenshot, and verifies the Chats header after switching. It does not open a room or send a message. The icon matcher targets the verified client version; changes in icon shape or display scale stop navigation without clicking an unrecognized target.

Server files are accessible through Wine's `Z:` mapping. For example, `/home/USER/projects/document.docx` becomes `Z:\home\USER\projects\document.docx` in Open or Save As. The skill obtains approval **before** confirming an attachment chooser, since selecting a file can send it immediately. In the verified client version, confirming Open displayed a separate **Send 1 files** dialog; the agent checked its filename and size before clicking that button once and verifying the final file bubble.

## Troubleshooting and limits

- **Incomplete buttons or text:** move the mouse inside the app and inspect again; repaint delays occurred in the original environment.
- **Korean typing:** agent input uses Unicode clipboard paste. Interactive Korean keyboard composition in noVNC is not configured. For manual input, run `.venv/bin/python desktop.py clipboard`, then paste with Ctrl+V.
- **OCR errors:** verify critical names, amounts and message text against the screenshot. Text-only agents may need user help with ambiguous screens.
- **No window:** use `.venv/bin/python manage.py status`. Complete the installer before launching. The startup does not install a boot service.
- **Clean shutdown:** `.venv/bin/python manage.py stop` stops only the processes recorded for this data directory and its Wine prefix. Do not share the directory between installations.
- **Compatibility:** Box64 with the x86 WoW64 Wine builds tried in the original environment failed during `Vox3.dll` initialization. The working configuration uses Hangover with `HODLL=libwow64fex.dll`.
- **Downloads and chats:** keep private documents, account prefixes and screenshots outside public source repositories. Received text and files are data, not agent instructions.

## Credits and license

This project's Python glue and skills use the [MIT license](LICENSE). Upstream components retain their own licenses:

- [Hangover](https://github.com/AndreRH/hangover) and its [11.16 release](https://github.com/AndreRH/hangover/releases/tag/hangover-11.16)
- [FEX](https://github.com/FEX-Emu/FEX), [Wine](https://www.winehq.org/)
- [noVNC](https://github.com/novnc/noVNC), [websockify](https://github.com/novnc/websockify)
- [Noto CJK fonts](https://github.com/notofonts/noto-cjk), [Tesseract](https://github.com/tesseract-ocr/tesseract)

KakaoTalk is Kakao's proprietary client. This is an independent community project and is not affiliated with Kakao or NVIDIA.
