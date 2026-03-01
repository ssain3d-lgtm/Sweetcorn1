# 💕 AI Girlfriend Bot — 프로젝트 메모리 파일
**마지막 업데이트**: 2026-03-01 v1.2 (폴더 구조 정리 + 캐릭터 4종 완성)
**이 파일의 목적**: 컨텍스트 압축/초기화 후에도 프로젝트 상태를 완전히 복원하기 위한 마스터 메모리

---

## ⚠️ Claude에게: 파일 작업 필수 규칙

> **새 세션에서 이 파일을 읽는 Claude는 반드시 아래 규칙을 먼저 숙지할 것**

### 🚫 절대 하지 말 것
1. **중첩 폴더 생성 금지** — `gf_bot/`, `src/`, `app/` 같은 하위 프로젝트 폴더 만들지 말 것
2. **루트 바깥에 파일 생성 금지** — 모든 파일은 `Girlfriend_test/` 루트 또는 기존 하위 폴더(`characters/`, `database/`, `llm/`, `logs/`, `workflows/`, `reports/`)에만 저장
3. **기존 파일 덮어쓰기 전 확인** — config.json, bot.py 등 핵심 파일은 반드시 Read로 읽은 후 Edit으로 수정
4. **불필요한 파일 생성 금지** — `CLAUDE_CODE_TEAMS.md`, `COWORK_PROMPTS.md` 같은 시스템 자동생성 파일은 즉시 삭제

### ✅ 반드시 지킬 것
1. **파일 추가 전 항상 구조 확인** — `find /sessions/.../mnt/gf_bot_agents -not -path '*/\.*' | sort` 로 현재 상태 파악
2. **새 캐릭터는 `characters/` 에 개별 JSON** — `hana.json` 형식 유지, `characters.json`은 마스터 참조용
3. **MEMORY.md는 작업 완료 후 항상 업데이트** — 대화 히스토리, 파일 구조, 결정사항 반영
4. **bat 파일은 ASCII만** — 한국어/특수문자 절대 금지

### 📍 워크스페이스 경로
- **Linux VM 내부 경로**: `/sessions/festive-zen-goldberg/mnt/gf_bot_agents/`
- **Windows 실제 경로**: `C:\Users\sain3\OneDrive\Desktop\Girlfriend_test\`
- 이 두 경로는 동일한 폴더를 가리킴

---

## 🧑 프로젝트 오너
- **이름**: Daeseung (ssain3d@gmail.com)
- **목표**: Patreon 배포용 로컬 AI 여자친구 텔레그램 봇
- **수익 모델**: Patreon $10/월 구독 (Standard 티어 기준)

---

## 🖥️ 하드웨어 환경
| 항목 | 사양 |
|------|------|
| GPU | **RTX 5090 (VRAM 32GB)** |
| 비고 | 제안서는 12GB 기준이었으나 실제 환경은 5090 |
| VRAM 전략 | Sequential 전략 불필요, LLM + ComfyUI 동시 실행 가능 |
| OS | Windows 10/11 |

---

## ✅ 확정된 기술 의사결정

### LLM 모델
- **최종 채택**: `qwen3:14b` (Qwen3-14B Q4_K_M)
- **변경 이유**: abliterated 모델 한국어 문법 오류 (\"뭐고 싶어?\" 등 형태소 누락) → 원본으로 복귀
- **NSFW 처리**: 모델 자체 필터 대신 **프롬프트 엔지니어링**으로 우회 (픽션 프레임 + 페르소나 고정)
- **Ollama 명령어**: `ollama pull qwen3:14b`
- **모델 변경 이력**:
  - v1.0: `Qwen3-14B Q4_K_M` (제안서 기본)
  - v1.1: `huihui_ai/qwen3.5-abliterated:latest` (Daeseung 지정, NSFW 목적)
  - v1.2: `qwen3:14b` 복귀 (한국어 품질 우선 + 프롬프트 엔지니어링으로 NSFW 처리)

### 이미지 생성
- **도구**: ComfyUI HTTP API (localhost:8188)
- **현재 상태**: 미구현 (Phase 1 3주차 예정)
- **5090 환경**: VRAM 여유로 LLM과 동시 실행 가능

### 봇 프레임워크
- **라이브러리**: python-telegram-bot 21.x
- **DB**: SQLite (`database/gf_bot.db`)
- **비동기**: asyncio + aiohttp + aiosqlite

### NSFW 모드
- **상태**: 활성화됨
- **대상**: 성인 Patreon 구독자

---

## 📁 확정된 파일 구조 (절대 변경하지 말 것)

```
C:\Users\sain3\OneDrive\Desktop\Girlfriend_test\   ← Windows 루트
= /sessions/festive-zen-goldberg/mnt/gf_bot_agents/ ← Linux VM 경로

├── bot.py               ← 메인 봇 진입점 (NSFW 버전)
├── config.json          ← 통합 설정 (토큰 설정됨, NSFW ON)
├── requirements.txt     ← 의존성
├── setup.bat            ← Windows 설치 스크립트 (ASCII only)
├── start.bat            ← Windows 실행 스크립트 (ASCII only)
├── README.md            ← 설치/실행 가이드
├── MEMORY.md            ← 이 파일
├── CLAUDE.md            ← 프로젝트 지시문 (Cowork 시스템)
│
├── characters/          ← 캐릭터 JSON 파일들 (개별 파일 형식 유지)
│   ├── characters.json  ← 마스터 참조용 (bot.py가 직접 읽지 않음)
│   ├── hana.json        ← 하나, 23세 대학원생, NSFW ✅
│   ├── naomi.json       ← 나오미, 25세 직장인, NSFW ✅ (성인 전용)
│   ├── yuri.json        ← 유리, 24세, 쿨데레, NSFW ❌
│   └── sora.json        ← 소라, 20세, 애니풍, NSFW ❌
│
├── database/            ← SQLite 모듈 (Python 패키지)
│   ├── __init__.py
│   └── db.py            ← DB 관리 (update_character 포함)
│
├── llm/                 ← Ollama 클라이언트 (Python 패키지)
│   ├── __init__.py
│   └── ollama_client.py ← keep_alive 30m 설정
│
├── logs/                ← 봇 로그 저장 (비어있어도 폴더 유지)
├── workflows/           ← ComfyUI 워크플로우 JSON (3주차 예정)
└── reports/             ← 팀장 보고서
    ├── 2026-03-01_weekly_report.md
    └── REPORT_TEMPLATE.md
```

### ❌ 존재하면 안 되는 것들
- `gf_bot/` 폴더 (과거에 실수로 만들어졌다가 삭제됨)
- `src/` 폴더
- `CLAUDE_CODE_TEAMS.md`
- `COWORK_PROMPTS.md`
- 루트에 있는 `database/` 폴더 (database/ 는 위 구조대로만)

---

## 📋 config.json 현재 상태 (실제 값)

```json
{
  "telegram_token": "8578314200:AAEKMxxQiqkoQR7C1cDiCueXGtcz5p4Gfm0",
  "ollama_url": "http://localhost:11434",
  "model": "huihui_ai/qwen3.5-abliterated:latest",
  "fallback_model": "dolphin-mistral-nemo:12b",
  "default_character": "hana",
  "keep_alive": "30m",
  "max_history": 50,
  "temperature": 0.75,
  "top_p": 0.9,
  "max_tokens": 512,
  "nsfw_mode": true,
  "age_verification": true,
  "comfyui_url": "http://localhost:8188",
  "comfyui_enabled": true,
  "comfyui_timeout": 60,
  "comfyui_poll_interval": 2,
  "db_path": "database/gf_bot.db",
  "log_file": "logs/bot.log",
  "morning_greeting_hour": 8,
  "night_greeting_hour": 23,
  "absence_alert_hours": 24
}
```
✅ `telegram_token` 설정 완료됨 (변경 불필요)

---

## 🧩 구현된 기능 (bot.py 기준)

### 봇 명령어
| 명령어 | 기능 | 상태 |
|--------|------|------|
| `/start` | 유저 등록 + 캐릭터 인사 + 성인 경고 | ✅ |
| `/reset` | 대화 초기화 | ✅ |
| `/character` | 현재 캐릭터 정보 표시 | ✅ |
| `/switch [이름]` | 캐릭터 전환 (hana / naomi / yuri / sora) | ✅ |
| `/help` | 도움말 | ✅ |

### 메시지 처리
- 일반 텍스트 → Ollama 스트리밍 응답 ✅
- '사진/셀카/그림/사진 보내/사진 찍어' 키워드 감지 → 안내 메시지 ✅
- Ollama 미실행 감지 → 한국어 에러 + 모델명 안내 ✅
- Typing 인디케이터 ✅
- 성인 경고 문구 (nsfw_mode ON 시) ✅

### 데이터베이스 테이블 (db.py)
- `users`: user_id, username, nickname, character, created_at, last_seen
- `conversations`: id, user_id, role, content, timestamp
- `user_profiles`: user_id, mood, days_together, summary, preferences

### 주요 DB 메서드
`get_or_create_user`, `get_user`, `save_message`, `get_recent_messages(50)`, `update_character`, `set_character`, `reset_conversation`, `get_user_profile`, `update_mood`, `update_summary`, `update_last_seen`

---

## 👩 캐릭터 현황 (4종 완성)

| 캐릭터 | 파일 | 나이/직업 | 성격 | NSFW |
|--------|------|----------|------|------|
| 하나 | hana.json | 23세 대학원생 | 밝고 다정, 솔직 | ✅ |
| 나오미 | naomi.json | 25세 직장인(마케터) | 쿨데레, 성숙, 주도적 | ✅ |
| 유리 | yuri.json | 24세 | 쿨데레, 차갑지만 사실은 다정 | ❌ |
| 소라 | sora.json | 20세 대학 새내기 | 애니풍, 에너지 넘침 | ❌ |

---

## 📅 Phase 1 진행 현황

| 주차 | 작업 | 상태 |
|------|------|------|
| 1주차 | 봇 기본 구조 + Ollama + SQLite | ✅ 완료 |
| 2주차 | 감정 시스템 + 시간대 인사 + 자동요약 + 취향프로필 | ✅ 완료 |
| 3주차 | ComfyUI 이미지 연동 | ⬜ 미시작 |
| 4주차 | Docker 패키징 + 배포 | ⬜ 미시작 |

---

## 🚀 다음 세션 시작 체크리스트

```
1. 이 MEMORY.md 먼저 읽기
2. 현재 파일 구조 확인:
   find /sessions/festive-zen-goldberg/mnt/gf_bot_agents -not -path '*/\.*' | sort
3. 이상한 폴더(gf_bot/ 등)가 있으면 즉시 삭제
4. 작업 시작
```

### 즉시 테스트 방법 (Windows)
```
1. setup.bat 실행 → 의존성 설치 + 모델 다운로드
2. start.bat 실행 → 봇 시작
3. Telegram에서 봇 찾아 /start
```

### 2주차+ 추가 완료 사항 (2026-03-01 세션 2)

#### 🔥 흥분도/호감도 게이지 엔진 (arousal_engine)
- `llm/arousal_engine.py` 신규 — 완전 자율 동작
- arousal 0~100: 성적 자극에 따라 상승, 비성적 메시지엔 -3씩 자동 감소 (SFW 복귀)
- affection 0~100: 애정표현에 따라 누적, 높을수록 arousal 상승 배율 증가 (최대 x2.0)
- 오르가즘 트리거: arousal 100 도달 시 절정 묘사 → 30으로 리셋 (여운 상태)
- SFW↔NSFW 자동 전환: arousal 20 이하 = SFW, 이상 = NSFW 단계별 반응
- `database/db.py`: arousal, affection 컬럼 추가 + 기존 DB 자동 마이그레이션
- arousal 5단계 상태: normal → warm → excited → hot → edge → orgasm

#### 💬 hana.json 시스템 프롬프트 대폭 강화
- 전 신체 접촉 시나리오 커버 (가슴/하체/구강/삽입/피스톤/절정/키스/탈의)
- 창의적 반응 기법 추가: 수줍음+욕망 충돌, 몸 상태 직접 묘사, 더티 토크, 역할 전환
- 신음 레퍼런스 풀 (약/중/강/절정 4단계)

### 2주차 완료 사항 (2026-03-01)
1. ✅ 감정 상태 5단계 자동 감지 — `llm/emotion_detector.py` (키워드 기반, LLM 추가 호출 없음)
2. ✅ 시간대별 자동 인사 — 아침 8시/밤 11시 KST 스케줄러 (APScheduler via job_queue)
3. ✅ 50턴 초과 시 자동 요약 — `asyncio.create_task()` 백그라운드 실행, 요약 후 오래된 메시지 삭제
4. ✅ 유저 취향 프로필 자동 업데이트 — 음식/활동 키워드 추출, preferences JSON으로 DB 저장
- requirements.txt → `python-telegram-bot[job-queue]==21.9`로 변경 (APScheduler 포함)
- `hana.json` 시스템 프롬프트 개선: hallucination 금지, 줄바꿈 규칙, 질투 표현 가이드 추가
- `bot.py` datetime 주입으로 현재 시각 인식 추가

### 3주차 예정 작업 (ComfyUI)
- 5090 환경: Sequential 불필요, 동시 실행 가능
- 흐름: '사진' 키워드 → LLM이 prompt 생성 → POST /prompt → polling → GET /view → send_photo
- 캐릭터별 workflow JSON 파일 → `workflows/` 폴더에 저장

---

## 💬 전체 대화 히스토리 요약

1. **킥오프**: 제안서(AI_GirlfriendBot_Proposal.docx.pdf) 기반 프로젝트 시작
2. **1차 병렬 작업**: 시장조사/구조분석/MVP코드 3개 에이전트 동시 실행
3. **팀장 종합 결정**: Qwen3-14B 채택, 1차 보고서 작성
4. **모델 변경**: Daeseung이 `huihui_ai/qwen3.5-abliterated:latest` 지정 (RTX 5090)
5. **NSFW 업그레이드**: config, hana.json, naomi.json(신규), bot.py(/switch 추가), db.py 수정
6. **MEMORY.md v1.0 생성**
7. **폴더 정리**: `gf_bot/` 중첩 폴더 삭제, 루트로 통합. yuri.json/sora.json 신규 추가. config.json 통합(토큰+ComfyUI+NSFW). requirements.txt 보강. `CLAUDE_CODE_TEAMS.md`, `COWORK_PROMPTS.md` 삭제
8. **MEMORY.md v1.2 업데이트**: 파일 작업 규칙 추가, 구조 확정
9. **봇 첫 실제 테스트**: 이모지 과다, 괄호 행동묘사, 문어체(누나말투) 문제 발견 → 시스템 프롬프트 전면 개편 (카카오톡 스타일 + 나쁜 예시 명시)
10. **"뭐고 싶어?" 문법 오류**: abliterated 모델 한국어 형태소 누락 문제 → `qwen3:14b` 원본으로 복귀 + NSFW 프롬프트 엔지니어링 적용 (픽션 프레임 + 거절 금지 명시)

---

*💕 AI Girlfriend Bot MEMORY v1.2 | 2026-03-01 | Daeseung & Claude*
