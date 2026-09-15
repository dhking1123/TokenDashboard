# TokenDashboard

Windows용 비공식 Codex 사용량 위젯입니다. 레트로 픽셀 UI로 주간 사용량과 선택적인 5시간 사용량을 표시합니다. OpenAI 공식 제품이 아닙니다.

## 다운로드 및 실행

1. [Releases](https://github.com/dhking1123/TokenDashboard/releases)에서 최신 Windows x64 ZIP을 받습니다.
2. 압축을 풀고 `CodexUsageDashboard.exe`를 실행합니다. Python 설치는 필요하지 않습니다.
3. 실행할 PC에 Codex가 설치되어 있고 본인 계정으로 로그인되어 있어야 합니다.

개인 제작·미서명 EXE이므로 Windows 보안 경고가 나타날 수 있습니다. 신뢰할 수 있는 출처인지 확인하세요.

## 사용법

- WEEK 기본 표시. 상단 토글로 5시간 영역을 추가하거나 숨깁니다.
- 일반·미니멀 모두 WEEK 또는 5H 영역을 더블클릭하면 해당 항목의 표시가 바뀝니다.
- **USED**: 사용량을 왼쪽부터 채움. **LEFT**: 잔여량을 오른쪽부터 채움.
- 잔여 100%는 체크 표시, 완전 소진은 자물쇠로 표시합니다.
- 실제 사용량 70% 이상은 노란색, 90% 이상은 빨간색입니다. 화이트 모드는 숫자에 테두리를 표시합니다.
- 상단 화살표: 일반·미니멀 전환. 오른쪽 상단 위치를 유지합니다.
- 하단 새로고침 / 테마 버튼. 자동 조회 간격은 30초입니다.
- 테마, 5H 표시 여부, 항목별 USED/LEFT 선택을 저장합니다.

설정은 EXE 실행 시 `%LOCALAPPDATA%\CodexUsageDashboard\settings.json`, 소스 실행 시 소스 옆 `usage-dashboard-settings.json`에 저장됩니다.

## 데이터와 제한

설치된 `codex app-server`를 통해 `account/read`, `account/rateLimits/read`, `account/usage/read`를 조회합니다. 모델에 프롬프트를 보내거나 응답 생성을 요청하지 않습니다. 로그인 정보나 개인 사용 기록은 배포 파일에 포함하지 않습니다.

5시간 본 한도가 있으면 CODEX, 별도 Spark 한도를 사용하는 경우 SPARK로 구분합니다. 데이터가 없거나 조회가 실패하면 `--`로 표시합니다. TOKENS는 서버가 반환한 누적값이며 남은 구독 토큰 수가 아닙니다.

Codex 버전·계정·플랜에 따라 제공되는 데이터가 다를 수 있습니다. 내부 조회 인터페이스가 변경되면 앱 업데이트가 필요할 수 있으며, 모든 플랜·버전에서의 호환성을 보장하지 않습니다. Windows 11 x64에서 검증했습니다.

## 개발 / 재빌드

Windows, Python 3.12 기준:

```powershell
python -m pip install -r requirements.txt
python usage-dashboard.py
python test_release.py
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

결과는 `dist/`에 생성됩니다. 테스트는 실제 계정 조회 없이 UI 이벤트·표시·설정을 검사합니다. 실제 로그인 상태 조회 점검은 `python usage-dashboard.py --check`입니다.

`CodexUsageDashboard.spec`는 외부 프로그램의 DLL이 섞이지 않도록 빌드 경로를 제한하고 Qt와 호환되는 VC 런타임을 포함합니다.

## 구성

- `usage-dashboard.py`: 조회 및 UI
- `CodexUsageDashboard.spec`, `build.ps1`, `requirements.txt`: EXE 재빌드
- `test_release.py`: 회귀 테스트
- `battery.ico`: 배터리 아이콘
- `THIRD_PARTY.txt` 및 라이선스 문서: 포함 라이브러리 안내

공유할 때는 라이선스 안내와 재빌드용 소스가 포함된 ZIP 사용을 권장합니다.
