# DGX Spark에서 카카오톡 사용하기

공식 Windows 카카오톡을 ARM64 Linux에서 실행하고, Claude Code와 Codex가 화면을 보며 조작하는 프로젝트입니다. Hangover + FEX, 전용 Xvfb 화면, noVNC, stdio MCP를 연결합니다. `/카카오톡` 스킬도 포함되어 있습니다.

## 확인한 기능

실제 DGX Spark 환경에서 QR 로그인, 대화 읽기, 한글 붙여넣기, 승인 후 메시지 전송, 받은 DOCX 다운로드를 확인했습니다. 로컬 한글·영문 OCR을 제공해 이미지 입력이 없는 에이전트도 화면의 글자를 읽을 수 있습니다.

서버 파일 첨부 절차는 스킬에 포함되어 있으며 파일 선택 창과 Linux 경로 접근을 확인했습니다. 실제 첨부 업로드와 새 설치 스크립트의 다른 장비 설치는 아직 확인하지 않았습니다.

## 설치와 로그인

Ubuntu 24.04 ARM64와 Python 3.12를 대상으로 합니다. [영문 README의 설치 명령](README.md#install)을 실행한 뒤 noVNC에서 공식 설치 프로그램을 완료하세요.

서버 브라우저 주소는 `http://127.0.0.1:6086/vnc.html`입니다. 다른 PC에서는 SSH로 연결합니다.

```bash
ssh -L 6086:127.0.0.1:6086 USER@SERVER
```

같은 localhost 주소를 브라우저에서 열고 화면 비밀번호를 입력하세요. sudo 비밀번호와는 별개이며, 서버 터미널에서 직접 확인할 수 있습니다.

```bash
cat ~/.local/share/kakaotalk-dgx-spark/vnc-password.txt
```

카카오톡의 **QR Code Log In**을 누르고 휴대폰에서 로그인·PC 인증을 완료합니다. 계정 비밀번호를 에이전트에게 전달할 필요는 없습니다.

## Claude Code·Codex 연결

저장소 폴더에서 실행하세요.

```bash
.venv/bin/python install_skill.py both
codex mcp add kakao-desktop -- "$PWD/.venv/bin/python" "$PWD/mcp_server.py"
claude mcp add --scope user --transport stdio kakao-desktop \
  -- "$PWD/.venv/bin/python" "$PWD/mcp_server.py"
```

새 세션에서 `/카카오톡`을 호출하세요. 예를 들면 다음처럼 요청할 수 있습니다.

```text
/카카오톡 지정한 방의 최근 메시지를 읽어줘.
/카카오톡 답장을 준비하고 전송 전에 내 승인을 받아줘.
/카카오톡 새로 받은 DOCX를 내 프로젝트 폴더에 저장해줘.
/카카오톡 서버의 /절대경로/문서.pdf를 첨부해줘. 전송 전에 확인해줘.
```

스킬은 받는 방과 정확한 문장 또는 파일명·경로·크기를 보여 주고 명시적 승인을 받은 뒤 전송합니다. 파일 선택만으로 전송되는 경우가 있어 선택 창의 Open도 승인 후에 누르도록 합니다. 이 절차는 에이전트 지침이며, 임의의 화면 조작을 기술적으로 차단하는 기능은 아닙니다.

계정 데이터와 인증 파일은 기본적으로 `~/.local/share/kakaotalk-dgx-spark/`에 저장됩니다. 전용 화면은 한 번에 한 사용자 또는 에이전트가 조작하세요. PC에 동기화된 대화만 읽을 수 있고, 방을 열면 읽음 표시가 바뀔 수 있습니다. 한글은 Unicode 붙여넣기로 입력하며 noVNC에서 직접 한글을 조합하는 입력기는 구성하지 않았습니다.

실행·종료·설정과 제한은 [영문 README](README.md)를 참고하세요. 프로젝트 코드와 스킬은 MIT 라이선스이며, 공식 앱과 각 실행 구성요소는 원래 라이선스를 따릅니다.
