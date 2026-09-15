# TokenDashboard for macOS

## 설치

- Apple Silicon(M1/M2/M3 등): `TokenDashboard-macOS-arm64.zip`
- Intel Mac: `TokenDashboard-macOS-x86_64.zip`
- macOS 13 이상이 필요합니다. 압축을 풀고 `TokenDashboard.app`을 응용 프로그램 폴더로 옮겨 실행하세요. Python은 필요하지 않습니다.
- Codex 앱 또는 CLI가 설치되고 본인 계정으로 로그인되어 있어야 합니다. 사용량 조회 인터페이스는 Codex 버전에 따라 다를 수 있습니다.

## 보안 안내

이 앱은 비공식 개인 제작 앱입니다. 로컬 실행용 ad-hoc 서명만 있으며 Apple Developer ID 서명·공증은 없습니다. 따라서 첫 실행 시 macOS가 차단할 수 있습니다. 출처를 신뢰할 때만 시스템 설정 → 개인정보 보호 및 보안에서 해당 앱의 실행을 개별 승인하세요. 시스템 전체 보안 설정은 끄지 마세요. 관리되는 회사 Mac에서는 관리자 정책에 따라 실행할 수 없을 수 있습니다.

## 사용법

- WEEK 기본, 상단 토글로 5시간 영역 표시
- 일반·미니멀 모두 각 영역 더블클릭: USED 사용량 ↔ LEFT 잔여량
- 사용량은 왼쪽부터, 잔여량은 오른쪽부터 채움
- 잔여 100% 체크, 완전 소진 자물쇠
- 30초 자동 조회, 다크·화이트 전환, 항상 위 표시
- 설정: `~/Library/Application Support/TokenDashboard/settings.json`

## Codex를 못 찾는 경우

Finder 실행 시 터미널 PATH가 전달되지 않을 수 있어 `/Applications/Codex.app`, `~/Applications/Codex.app`, `/opt/homebrew/bin/codex`, `/usr/local/bin/codex`, `~/.local/bin/codex`를 추가로 확인합니다. 사용자 지정 경로에 CLI를 설치했다면 해당 PATH가 설정된 터미널에서 앱 내부 실행 파일을 실행하거나, 표준 경로에 Codex를 설치하세요.

## 검증 범위

GitHub의 실제 macOS 러너에서 각 CPU용 앱 빌드, UI 회귀 테스트 및 패키지 실행 테스트를 수행합니다. 테스트에 개인 인증정보를 넣지 않으므로 실제 Mac 계정의 로그인·사용량 조회와 Gatekeeper 승인 과정은 별도로 확인해야 합니다. 조회 불가 시 `--`로 표시됩니다.

## 재빌드

첨부된 `source` 폴더에서 Python 3.12와 Xcode Command Line Tools가 설치된 Mac으로 실행합니다.

```bash
python3 -m pip install -r requirements.txt
bash build-macos.sh
```

소스 폴더에서 재빌드할 때는 상위 폴더의 `README-macOS.md`, `THIRD_PARTY.txt`, 라이선스 TXT 파일도 소스 폴더로 복사하세요. 필요한 전체 소스는 GitHub 저장소에도 있습니다.
