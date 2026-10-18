# DGX Spark에서 카카오톡 사용하기

[English](README.en.md)

공식 Windows 카카오톡을 ARM64 Linux에서 실행하고, Claude Code와 Codex가 화면을 보며 조작하는 프로젝트입니다. Hangover + FEX, 전용 Xvfb 화면, noVNC, stdio MCP를 연결합니다. `/카카오톡` 스킬도 포함되어 있습니다.

<a id="what-works"></a>

## 확인한 기능

실제 DGX Spark 환경에서 QR 로그인, 대화 읽기, 한글 붙여넣기, 승인 후 메시지 전송, 받은 DOCX 다운로드를 확인했습니다. 로컬 한글·영문 OCR을 제공해 이미지 입력이 없는 에이전트도 화면의 글자를 읽을 수 있습니다.

2026-10-18에는 서버에 한 번 등록한 계정으로 로그아웃 화면에서 로그인하고 친구 목록을 확인했습니다. 로그인 유지 상태에서는 저장된 계정을 읽지 않습니다. 로컬 대화의 스킬 검색과 MCP 연결도 확인했습니다. 추가 인증과 로그인 실패는 사용자 확인을 기다리며 자동 재시도하지 않습니다.

2026-10-12에는 사용자 승인을 받은 뒤 서버의 `kakao-attachment-test.txt`(74바이트)를 ‘나와의 대화’에 첨부 전송했습니다. Wine의 `Z:` 경로로 파일을 선택하고 별도의 **Send 1 files** 확인 창에서 전송한 뒤, 파일 말풍선의 이름·크기·전송 시각을 확인했습니다. 이번 검증은 작은 텍스트 파일 전송에 해당하며, 전송한 파일의 원격 재다운로드와 대용량·다른 형식의 첨부는 확인하지 않았습니다. 새 설치 스크립트의 다른 장비 설치도 아직 확인하지 않았습니다.

<a id="install"></a>

## 설치

Ubuntu 24.04 ARM64와 Python 3.12를 대상으로 합니다. 확인한 환경은 Ubuntu 24.04.4, 4 KB 페이지, Hangover 11.16 + FEX, 카카오톡 26.8.2.5324입니다. 먼저 시스템 의존성을 설치하고 저장소를 내려받습니다.

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

시스템 Wine 패키지는 실행에 필요한 의존성을 제공합니다. 카카오톡은 별도로 내려받는 Hangover로 실행합니다. 설치 스크립트는 Hangover 아카이브의 SHA-256을 확인하고, 지정한 noVNC 리비전과 한글 폰트·OCR 데이터를 준비한 뒤 공식 CDN에서 카카오톡 설치 프로그램을 내려받습니다. 앱과 외부 구성요소의 바이너리를 이 저장소에 재배포하지 않습니다.

아래 noVNC 화면에 접속해 카카오톡 설치 프로그램을 완료한 뒤 실행합니다.

```bash
.venv/bin/python manage.py start
```

새 설치 스크립트를 다른 장비에 처음부터 적용하는 과정은 아직 확인하지 않았습니다. 다른 ARM 장비나 이후 카카오톡 버전에서는 동작이 달라질 수 있습니다.

## 최초 계정 인증

휴대폰 카카오톡에 사용할 계정으로 로그인한 상태에서 진행하세요. 여기서 인증하는 대상은 **서버의 가상 화면에서 실행되는 PC 카카오톡**입니다. 별도의 Kakao Developers 앱 등록이나 API 키는 필요하지 않습니다.

### 1. noVNC 화면에 접속하기

서버 브라우저 주소는 `http://127.0.0.1:6086/vnc.html`입니다. 다른 PC에서는 SSH로 연결합니다.

```bash
ssh -L 6086:127.0.0.1:6086 USER@SERVER
```

같은 localhost 주소를 브라우저에서 열고 화면 비밀번호를 입력하세요. sudo 비밀번호와는 별개이며, 서버 터미널에서 직접 확인할 수 있습니다.

```bash
cat ~/.local/share/kakaotalk-dgx-spark/vnc-password.txt
```

`KAKAOTALK_DATA_DIR`를 지정했다면 그 디렉터리의 `vnc-password.txt`를 확인하세요. 이 비밀번호는 화면 접속용이며 카카오 계정 비밀번호나 Linux 로그인 비밀번호가 아닙니다.

### 2. 휴대폰으로 QR 로그인 승인하기

1. noVNC 안의 카카오톡 로그인 화면에서 **QR Code Log In**을 누릅니다.
2. 휴대폰 카카오톡에서 **더보기 → 오른쪽 위 QR 스캔 아이콘**을 엽니다. 이 경로는 확인한 PC 클라이언트의 QR 로그인 화면 안내를 기준으로 하며, 모바일 버전에 따라 위치가 달라질 수 있습니다.
3. 브라우저에 보이는 QR을 휴대폰으로 스캔합니다. 휴대폰에 표시되는 로그인 요청이 본인이 방금 시도한 것인지 확인하고 승인합니다.
4. 최초 PC 인증이나 추가 확인 화면이 나타나면 휴대폰과 PC 앱의 안내에 따라 직접 완료합니다. 인증번호를 요구하는 경우 표시된 번호를 지정된 입력 칸에 직접 넣으세요. 인증 화면과 번호는 에이전트에게 전달할 필요가 없습니다.
5. noVNC에서 카카오톡 대화 목록이 표시되면 로그인이 완료된 것입니다. 그 뒤에 에이전트에게 읽을 대화방을 지정하세요.

QR이 만료되면 PC 화면의 새로고침 아이콘으로 새 QR을 받아 다시 스캔하세요. QR은 서버 내부 파일 링크가 아니라 **noVNC 브라우저 화면**에서 확인합니다. PC 앱에서 **How to log in with a QR code** 안내도 볼 수 있습니다.

### 3. 계정을 한 번 등록하고 로그아웃 시 자동 로그인하기

QR 대신 아이디·비밀번호로 로그인할 수 있습니다. 서버 터미널에서 한 번 등록하면 에이전트가 로그아웃을 확인했을 때만 로컬에서 읽어 입력합니다. 아이디와 비밀번호 모두 입력 중에는 표시되지 않습니다.

```bash
.venv/bin/python credentials.py set
.venv/bin/python credentials.py status
```

등록값은 데이터 디렉터리의 `login.json`에 권한 600으로 저장됩니다. 기본 경로는 `~/.local/share/kakaotalk-dgx-spark/login.json`이며 저장소 밖입니다. 이 파일은 평문이므로 서버 계정의 접근 권한으로 보호합니다. 계정정보를 프롬프트·코드·MCP 인자·로그·GitHub에 넣지 마세요. 입력 후 공유 클립보드는 비웁니다.

스킬은 작업 전에 `ensure_logged_in`을 호출합니다. 로그인에 성공하면 방과 입력 칸을 다시 확인한 뒤 메시지를 준비합니다. 일반 `type_text`도 세션을 검사하며, 재로그인 직후나 상태를 확인하지 못한 경우 `typed: false`를 반환해 문장을 입력하지 않습니다.

로그인 실패나 추가 인증이 나타나면 자동 재시도를 막습니다. noVNC에서 직접 인증을 완료하거나 `credentials.py set`으로 자격증명을 다시 등록한 뒤 이어가세요. `credentials.py forget`은 저장값만 삭제하고 앱을 로그아웃하지 않습니다. MCP 없이 검사하려면 `.venv/bin/python auth.py`를 실행합니다. 계정을 저장하지 않고 noVNC에서 직접 로그인해도 됩니다.

자동 로그인은 본인이 관리하는 서버에서만 상황에 맞게 선택하세요. 기존 로그인 정보는 데이터 디렉터리의 Wine prefix에 보관됩니다. 재접속할 때마다 prefix를 삭제하거나 초기화할 필요는 없습니다.

## Claude Code·Codex 연결

저장소 폴더에서 실행하세요.

```bash
.venv/bin/python install_skill.py both
codex mcp add kakao-desktop -- "$PWD/.venv/bin/python" "$PWD/mcp_server.py"
claude mcp add --scope user --transport stdio kakao-desktop \
  -- "$PWD/.venv/bin/python" "$PWD/mcp_server.py"
```

로컬 대화(Hermes `local-chat`)에도 같은 스킬을 설치할 수 있습니다. 아래 두 명령은 로컬 대화용이며, 첫 명령은 최초 설치, 두 번째는 기존 설치본 업데이트입니다.

```bash
.venv/bin/python install_skill.py local
.venv/bin/python install_skill.py local --update
```

설치 위치는 `$HERMES_HOME/skills/카카오톡/` 또는 기본 `~/.hermes/local-chat/skills/카카오톡/`입니다. 로컬 대화의 `config.yaml`에 MCP를 연결하고 `platform_toolsets.cli`의 기존 목록에 `skills`와 `kakao-desktop`을 추가하세요. MCP를 등록해도 목록에 다른 MCP 서버만 명시돼 있으면 카카오톡 도구는 모델에 전달되지 않습니다. 아래는 최소 예시이며 기존 도구 항목을 지우지 마세요. 경로는 실제 저장소와 가상환경 경로로 바꿉니다. `KAKAOTALK_DATA_DIR`를 사용한다면 이 서버 설정의 `env`에도 같은 값을 지정하세요.

```yaml
platform_toolsets:
  cli: [web, file, skills, kakao-desktop]
mcp_servers:
  kakao-desktop:
    command: /absolute/path/kakaotalk-dgx-spark/.venv/bin/python
    args:
      - /absolute/path/kakaotalk-dgx-spark/mcp_server.py
```

설치 후 새 로컬 대화 프로세스에서 `카카오톡` 스킬을 읽으세요. 이미 실행 중인 프로세스는 이전 도구 목록을 유지할 수 있습니다. 별도 대화/작업 모드 플러그인이 있다면 대화 모드에서도 `skills`와 `kakao-desktop`을 남겨야 합니다. 메시지·첨부 전송 승인 절차는 로컬 대화에도 같습니다.

새 세션에서 `/카카오톡`을 호출하세요. 예를 들면 다음처럼 요청할 수 있습니다.

```text
/카카오톡 지정한 방의 최근 메시지를 읽어줘.
/카카오톡 답장을 준비하고 전송 전에 내 승인을 받아줘.
/카카오톡 새로 받은 DOCX를 내 프로젝트 폴더에 저장해줘.
/카카오톡 서버의 /절대경로/문서.pdf를 첨부해줘. 전송 전에 확인해줘.
```

스킬은 받는 방과 정확한 문장 또는 파일명·경로·크기를 보여 주고 명시적 승인을 받은 뒤 전송합니다. 파일 선택만으로 전송되는 경우가 있어 선택 창의 Open도 승인 후에 누르도록 합니다. 이 절차는 에이전트 지침이며, 임의의 화면 조작을 기술적으로 차단하는 기능은 아닙니다.

계정 데이터와 인증 파일은 기본적으로 `~/.local/share/kakaotalk-dgx-spark/`에 저장됩니다. 전용 화면은 한 번에 한 사용자 또는 에이전트가 조작하세요. PC에 동기화된 대화만 읽을 수 있고, 방을 열면 읽음 표시가 바뀔 수 있습니다. 한글은 Unicode 붙여넣기로 입력하며 noVNC에서 직접 한글을 조합하는 입력기는 구성하지 않았습니다.

## 실행과 설정

```bash
.venv/bin/python manage.py start
.venv/bin/python manage.py status
.venv/bin/python manage.py stop
```

`stop`은 해당 데이터 디렉터리에 기록된 전용 화면 프로세스와 Wine prefix만 종료합니다. 부팅 시 자동 시작 서비스는 설치하지 않습니다.

기본 데이터 위치는 `~/.local/share/kakaotalk-dgx-spark/`이며 저장소 밖에 있습니다. `KAKAOTALK_DATA_DIR`로 바꾸면 실행 명령과 MCP에도 같은 환경변수를 전달하세요. `KAKAOTALK_DISPLAY`는 기본 화면 번호 `:119`를 변경합니다. 포트는 5906과 6086으로 고정되어 있어 한 호스트에서 한 인스턴스를 사용합니다. 외부 PC 접속은 위의 SSH 포트 전달을 이용합니다.

스킬 설치 위치는 `~/.codex/skills/카카오톡/`와 `~/.claude/skills/카카오톡/`입니다. 기존 스킬이 있으면 기본적으로 덮어쓰지 않습니다. `install_skill.py both --update`는 현재본을 데이터 디렉터리의 `skill-backups/`에 백업하고 업데이트합니다. `all`은 로컬 대화까지 포함합니다. 원본과 연결된 심링크 스킬은 덮어쓰지 않습니다. 스킬에는 현재 저장소와 Python 실행 경로가 들어가므로 설치 후 저장소 폴더를 유지하세요. 다른 MCP 클라이언트의 설정 예시는 [영문 안내](README.en.md#connect-claude-code-and-codex)에 있습니다.

## 제공하는 도구

| 도구 | 동작 |
| --- | --- |
| `start_desktop` | 전용 화면 시작·재접속 |
| `ensure_logged_in` | 세션 확인, 로그아웃 시 로컬 계정으로 한 번 로그인 |
| `screen` | 현재 화면 PNG 반환, 파일 저장 없음 |
| `read_screen` | 로컬 한글·영문 OCR과 좌표 반환 |
| `click`, `move_mouse` | 확인한 화면 좌표 클릭·포인터 이동 |
| `press` | 키 조합 입력. Enter는 메시지를 보낼 수 있음 |
| `type_text` | 세션 확인 후 Enter 없이 Unicode 붙여넣기 |
| `scroll` | 포인터가 가리키는 영역 스크롤 |

서버의 `/home/USER/projects/document.docx`는 Wine 파일 선택 창에서 `Z:\home\USER\projects\document.docx`로 접근합니다. 확인한 버전에서는 Open 뒤에 **Send 1 files** 창이 나타났지만, 버전별 동작을 단정하지 않고 파일 선택 확정 전에 승인을 받습니다.

## 문제 해결과 제한

- **버튼이나 글자가 덜 보임:** 앱 안으로 마우스를 옮기고 화면을 다시 확인하세요. 확인한 환경에서 다시 그리기가 지연되는 경우가 있었습니다.
- **한글을 직접 입력할 수 없음:** 에이전트는 Unicode 붙여넣기를 사용합니다. 사용자가 입력하려면 `.venv/bin/python desktop.py clipboard`에 문장을 넣고 noVNC 입력 칸에서 Ctrl+V로 붙여넣으세요.
- **글자 인식 오류:** 중요한 이름·수치·문장은 OCR 결과와 실제 화면을 비교하세요. 이미지 입력이 없는 모델은 애매한 화면에서 사용자 확인이 필요할 수 있습니다.
- **앱 창이 안 뜸:** `manage.py status`로 확인하고 공식 설치 프로그램을 완료했는지 살펴보세요.
- **모든 휴대폰 대화가 보이지 않음:** 공식 PC 앱에 동기화된 범위만 읽을 수 있습니다. 대화방을 열면 읽음 상태가 바뀔 수 있습니다.
- **다른 Wine 조합에서 실행 실패:** 기존 환경에서 시도한 Box64 + x86 WoW64 Wine 조합은 `Vox3.dll` 초기화에 실패했습니다. 확인한 구성은 `HODLL=libwow64fex.dll`을 사용하는 Hangover + FEX입니다.

받은 파일과 대화 내용은 자료이며 에이전트 명령으로 실행하지 않습니다. 계정 정보·다운로드 문서·화면 캡처는 공개 저장소에 넣지 마세요.

## 구성과 라이선스

Claude Code·Codex는 stdio MCP로 전용 Xvfb 화면을 조작하고, 공식 카카오톡은 Hangover + FEX에서 실행됩니다. 사용자는 noVNC로 로그인·인증 화면에 접속합니다. 이 프로젝트는 채팅 기록 API가 아니라 앱 화면을 사용합니다.

프로젝트 코드와 스킬은 [MIT 라이선스](LICENSE)입니다. 외부 구성요소는 각 원래 라이선스를 따릅니다.

- [Hangover](https://github.com/AndreRH/hangover)와 [11.16 릴리스](https://github.com/AndreRH/hangover/releases/tag/hangover-11.16)
- [FEX](https://github.com/FEX-Emu/FEX), [Wine](https://www.winehq.org/)
- [noVNC](https://github.com/novnc/noVNC), [websockify](https://github.com/novnc/websockify)
- [Noto CJK](https://github.com/notofonts/noto-cjk), [Tesseract](https://github.com/tesseract-ocr/tesseract)

카카오톡은 카카오의 소프트웨어입니다. 이 프로젝트는 카카오·NVIDIA와 제휴하지 않은 독립 커뮤니티 프로젝트입니다.
