# 💕 AI Girlfriend Telegram Bot — 프로젝트 컨텍스트

## 프로젝트 개요
Telegram 기반 AI 여자친구 봇. Patreon($10/월) 배포용 로컬 LLM 솔루션.

## 핵심 제약 조건 (절대 우선순위)
- GPU VRAM: **12GB 이하** (RTX 3060 Ti 기준)
- LLM: **Ollama** 기반 로컬 실행 (외부 API 불가)
- 이미지: **ComfyUI** API 연동 (사용자 제공 워크플로우 사용)
- 플랫폼: **python-telegram-bot 21.x**
- 배포: **Windows 설치 패키지** (Patreon 구독자용)

## 기술 스택
```
python-telegram-bot 21.x    # 텔레그램 봇
Ollama HTTP API             # LLM 서버 (localhost:11434)
ComfyUI HTTP API            # 이미지 생성 (localhost:8188)
SQLite + JSON               # 대화 메모리 / 유저 프로필
asyncio + aiohttp           # 비동기 처리
```

## 권장 LLM 모델 (VRAM 기준)
| 모델 | VRAM | 특징 |
|------|------|------|
| Qwen3-14B Q4_K_M | ~7.8GB | 한국어 우수, 롤플레이 강함 ← 1순위 |
| dolphin-mistral-nemo:12b | ~7.2GB | 무검열, 롤플레이 특화 ← 2순위 |
| gemma3:12b Q4_K_M | ~6.5GB | 자연스러운 대화체 |

## 프로젝트 폴더 구조
```
gf_bot/
├── bot.py                  # 메인 봇 진입점
├── config.json             # 설정 (토큰, 모델, ComfyUI 경로)
├── requirements.txt        # 의존성
├── database/
│   └── db.py              # SQLite 메모리 관리
├── llm/
│   └── ollama_client.py   # Ollama API 래퍼
├── image/
│   └── comfyui_client.py  # ComfyUI API 래퍼
├── characters/
│   ├── hana.json          # 하나 (기본 캐릭터)
│   ├── yuri.json          # 유리 (쿨데레)
│   ├── sora.json          # 소라 (애니)
│   └── naomi.json         # 나오미 (성인)
├── workflows/              # ComfyUI 워크플로우 JSON
│   ├── hana_workflow.json
│   └── ...
├── setup.bat              # Windows 설치 스크립트
└── start.bat              # 봇 시작 스크립트
```

## 여자친구 UX 핵심 원칙
1. 유저 이름/닉네임 기억 → 자연스럽게 호칭 사용
2. 감정 상태 5단계: happy / normal / pouty / excited / tired
3. 최근 50턴 대화 + 요약 저장 (SQLite)
4. '사진 보내줘' 감지 → ComfyUI 자동 트리거
5. 시간대별 인사 메시지 (아침/밤)
6. .bat 파일은 반드시 ASCII 문자만 사용 (한국어 금지)

## 현재 단계
- [x] 시장 조사 완료 ($2.8B 시장, 수요 폭증)
- [x] 시스템 아키텍처 설계 완료
- [x] 종합 제안서 작성 완료
- [ ] MVP Phase 1 구현 (현재 단계)
- [ ] ComfyUI 연동
- [ ] Patreon 배포 패키지

## 에이전트 역할 분담
- **시장조사 에이전트**: 경쟁사 모니터링, 유저 피드백 분석
- **구조분석 에이전트**: VRAM 최적화, 아키텍처 검토, 병목 분석
- **구현전문가 에이전트**: 실제 코드 작성, 디버깅, API 연동
- **팀장 에이전트**: 종합 조율, 의사결정, 주간 보고서 작성

## 보고서 저장 경로
`reports/` 폴더에 날짜별 Markdown 파일로 저장
예: `reports/2026-03-01_weekly_report.md`
