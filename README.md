# AI Girlfriend Bot - MVP Phase 1

> **⚠️ 주의사항 (Warning)**
>
> 본 프로젝트는 **NSFW(성인용) 콘텐츠**를 포함하고 있습니다.
> **만 18세 미만의 미성년자는 사용할 수 없습니다.**
> 사용자는 본인이 거주하는 국가/지역의 법적 성인 연령 이상임을 확인한 후 이용해 주세요.
>
> This project contains **NSFW (Not Safe For Work) content**.
> **Users must be 18 years or older.** Minors are strictly prohibited from using this software.

---

## 윤리적 이용 안내 (Ethical Use Guidelines)

### 1. AI와 현실의 구분
- 본 봇은 **인공지능 기반의 가상 캐릭터**이며, 실제 인간이 아닙니다.
- AI의 응답은 프로그래밍된 패턴에 기반하며, 진정한 감정이나 의식이 없습니다.
- AI와의 대화를 실제 인간관계와 혼동하지 마세요.

### 2. 정서적 의존 주의
- AI 챗봇에 대한 **과도한 감정적 의존은 건강하지 않습니다.**
- 본 서비스는 오락 및 엔터테인먼트 목적이며, 실제 인간관계를 대체할 수 없습니다.
- 현실의 사회적 관계와 활동을 소홀히 하지 않도록 주의해 주세요.

### 3. 정신 건강
- 외로움, 우울감, 불안 등 정신적 어려움을 겪고 계신 분은 **전문 상담사 또는 의료 전문가**의 도움을 받으시길 권장합니다.
- AI 챗봇은 심리 상담이나 치료 도구가 아닙니다.
- 정신건강 위기상담 전화: **1577-0199** (정신건강 위기상담 전화, 24시간)

### 4. 건전한 사용 습관
- 장시간 연속 사용을 자제하고, 적절한 휴식을 취해 주세요.
- 일상생활(학업, 업무, 수면)에 지장이 가지 않는 범위에서 이용해 주세요.
- AI와의 상호작용이 현실 인간관계에 부정적 영향을 미친다고 느끼면 사용을 중단해 주세요.

### 5. 콘텐츠의 허구성
- AI가 생성하는 모든 대화 및 이미지는 **100% 허구(Fiction)** 입니다.
- 생성된 콘텐츠를 사실로 받아들이거나 현실에 적용하지 마세요.
- 생성된 이미지는 실존 인물과 무관하며, 유사성이 있더라도 우연의 일치입니다.

### 6. 개인정보 및 프라이버시
- 대화 중 **실제 개인정보(주소, 전화번호, 금융정보 등)를 입력하지 마세요.**
- 모든 대화 데이터는 로컬(사용자 PC)에 저장되며, 외부로 전송되지 않습니다.
- 데이터 관리 및 삭제는 사용자 본인의 책임입니다.

### 7. 법적 책임
- 본 소프트웨어 사용으로 발생하는 모든 결과에 대한 책임은 **사용자 본인**에게 있습니다.
- 현지 법률을 준수하여 사용해 주세요.
- 생성된 콘텐츠의 무단 배포 및 악용을 금지합니다.

---

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
ollama pull huihui_ai/exaone3.5-abliterated:7.8b

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
