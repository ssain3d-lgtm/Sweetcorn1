# AI Girlfriend Bot - MVP Phase 1

Telegram 기반 AI 여자친구 봇 (Ollama 로컬 LLM 사용)

## 설치 및 실행

### 1. 필수 요구사항
- Python 3.8 이상
- Ollama (로컬 LLM 서버)
- Telegram Bot Token (BotFather 에서 생성)
- GPU 12GB 이상 (RTX 3060 Ti 권장)

### 2. Windows 설치

```batch
setup.bat
```

이 스크립트는 다음을 수행합니다:
- Python 버전 확인
- pip 의존성 설치 (python-telegram-bot, aiohttp 등)

### 3. Ollama 설정

```bash
# 1. Ollama 다운로드 및 설치
# https://ollama.ai 에서 다운로드

# 2. 권장 모델 다운로드
ollama pull qwen3:14b

# 3. Ollama 서버 실행
ollama serve
```

### 4. Telegram Bot Token 설정

1. Telegram 에서 @BotFather 를 찾아 메시지 전송
2. /newbot 명령어로 새 봇 생성
3. 받은 Token 을 config.json 의 `telegram_token` 에 입력

### 5. 봇 시작

```batch
start.bat
```

또는 CMD/PowerShell 에서:

```bash
python bot.py
```

## 구조

```
gf_bot/
├── bot.py                      # 메인 진입점
├── config.json                 # 설정 파일
├── requirements.txt            # 의존성
├── database/
│   ├── __init__.py
│   └── db.py                  # SQLite 메모리 관리
├── llm/
│   ├── __init__.py
│   └── ollama_client.py       # Ollama API 래퍼
├── characters/
│   └── hana.json              # 하나 캐릭터 프로필
├── setup.bat                   # Windows 설치 스크립트
└── start.bat                   # Windows 시작 스크립트
```

## 사용 명령어

- `/start` - 봇 시작 및 캐릭터 소개
- `/reset` - 대화 기록 초기화
- `/character` - 캐릭터 정보 및 프로필 표시
- `/help` - 도움말

## 특수 기능

- 사용자 이름 자동 기억 및 호칭 사용
- 최근 50턴 대화 히스토리 관리
- 감정 상태 (5단계: happy, normal, pouty, excited, tired)
- "사진 보내줘" 감지 (향후 ComfyUI 연동)

## 트러블슈팅

### Ollama 연결 불가
- Ollama 서버가 실행 중인지 확인: `http://localhost:11434` 접속 시도
- 방화벽 설정 확인
- 모델 다운로드 확인: `ollama list`

### 봇이 응답하지 않음
- config.json 에서 telegram_token 확인
- Python 로그 메시지 확인
- Ollama 서버 상태 확인

### VRAM 부족
- 더 작은 모델 사용:
  - dolphin-mistral-nemo:12b (~7.2GB)
  - gemma3:12b Q4_K_M (~6.5GB)
- config.json 에서 `model` 값 변경

## Ollama Keep-Alive 전략

프로젝트는 VRAM 최적화를 위해 Ollama의 `keep_alive` 파라미터를 활용합니다:

- **keep_alive: "10m"** (기본값)
  - 모델을 메모리에 유지하는 시간
  - 10분 후 자동으로 메모리에서 언로드
  - VRAM 사용량 최소화
  - 연속 대화 시 응답 속도 유지

이 설정으로 12GB GPU 내에서 안정적 운영 가능합니다.

## 라이선스

Patreon 배포용 (구독자용)

## 지원

문제가 있으시면 로그 파일을 확인하고 관리자에게 문의하세요.
