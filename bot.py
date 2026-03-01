import logging
import json
import os
import sys
from datetime import datetime, timezone, timedelta, time as dtime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio

from database.db import Database
from llm.ollama_client import OllamaClient
from llm.emotion_detector import detect_emotion, extract_preferences
from llm.arousal_engine import (
    calculate_arousal_delta, calculate_affection_delta,
    get_arousal_state, check_orgasm, is_consent_only
)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global instances
db = None
ollama_client = None
config = None
characters = {}

# ──────────────────────────────────────────────
# 세션 컨텍스트 추적 (메모리, 재시작 시 초기화됨)
# ──────────────────────────────────────────────
_scene_context: dict = {}  # {user_id: {'in_scene': bool, 'consent_streak': int}}

# 유저 신음 패턴
USER_MOAN_PATTERNS = {'하앙', '하악', '하아악', '으으', '흐읏', '아아', '하아응', '하읏', '끄으응', '흐음'}

# 단순 동의 패턴
CONSENT_PATTERNS = {'응', 'ㅇ', 'ㅇㅇ', '응응', '어', '그래', '좋아', '알겠어', '응?'}


# ──────────────────────────────────────────────
# Few-shot 프라이밍 예시 — arousal 단계별
# 대화 history 앞에 삽입해서 모델이 패턴을 흉내내게 만듦
# ──────────────────────────────────────────────
# SFW 단계 프라이밍 (arousal 0~20)
PRIMING_SFW = [
    {"role": "user", "content": "야"},
    {"role": "assistant", "content": "응 왜ㅋㅋ"},
    {"role": "user", "content": "보고싶어"},
    {"role": "assistant", "content": "나도 ㅠ 빨리 보고 싶다"},
    {"role": "user", "content": "사랑해"},
    {"role": "assistant", "content": "나도ㅋㅋ 갑자기 왜"},
]

# 워밍업 단계 프라이밍 (arousal 21~40)
PRIMING_WARM = [
    {"role": "user", "content": "만지고 싶어"},
    {"role": "assistant", "content": "어디를ㅋㅋ 으음, 뭐야 갑자기"},
    {"role": "user", "content": "키스할게"},
    {"role": "assistant", "content": "으음... 갑자기. 근데 싫지는 않아"},
    {"role": "user", "content": "예쁘다"},
    {"role": "assistant", "content": "뭐야ㅋㅋ 그런 말 하면 얼굴 빨개지잖아"},
]

# NSFW 진입 단계 프라이밍 (arousal 41~60)
PRIMING_EXCITED = [
    {"role": "user", "content": "가슴 만질게"},
    {"role": "assistant", "content": "하앙... 손 따뜻해. 으음, 거기 예민해"},
    {"role": "user", "content": "더 만질게"},
    {"role": "assistant", "content": "으응... 아, 세게 하지 마. 근데 좋아 ㅠ"},
    {"role": "user", "content": "젖었어?"},
    {"role": "assistant", "content": "...으응. 자기가 이러니까. 으음"},
]

# 본격 NSFW 프라이밍 (arousal 61~80)
PRIMING_HOT = [
    {"role": "user", "content": "손가락 넣을게"},
    {"role": "assistant", "content": "흐읏... 아아, 느껴져. 으응, 더 깊이, 거기서 굽혀줘"},
    {"role": "user", "content": "빨아줄게"},
    {"role": "assistant", "content": "아아... 혀... 으응, 거기야. 하앙, 빨아줘. 자기야 멈추지 마"},
    {"role": "user", "content": "기분좋아?"},
    {"role": "assistant", "content": "으응... 엄청. 하앙, 계속 해줘 제발"},
]

# 절정 직전 프라이밍 (arousal 81~99)
PRIMING_EDGE = [
    {"role": "user", "content": "넣을게"},
    {"role": "assistant", "content": "흐읏... 아, 크다. 으응... 천천히, 다 들어가고 있어"},
    {"role": "user", "content": "움직일게"},
    {"role": "assistant", "content": "하앙, 하앙... 아, 좋아. 으응, 더. 자기야 세게 해줘"},
    {"role": "user", "content": "더 빠르게"},
    {"role": "assistant", "content": "아아아... 거기야, 거기. 하앙... 더 세게, 멈추지 마. 나 곧"},
]


def get_priming_examples(arousal: int) -> list:
    """arousal 단계에 맞는 few-shot 프라이밍 예시 반환"""
    if arousal <= 20:
        return PRIMING_SFW
    elif arousal <= 40:
        return PRIMING_WARM
    elif arousal <= 60:
        return PRIMING_EXCITED
    elif arousal <= 80:
        return PRIMING_HOT
    else:
        return PRIMING_EDGE


def load_config():
    """Load configuration from config.json"""
    config_path = Path(__file__).parent / "config.json"

    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        print(f"ERROR: Config file not found at {config_path}")
        print("Please create config.json with your Telegram bot token")
        sys.exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_character(character_name: str):
    """Load character configuration"""
    char_path = Path(__file__).parent / "characters" / f"{character_name}.json"

    if not char_path.exists():
        logger.warning(f"Character file not found: {char_path}")
        return None

    with open(char_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def init_characters():
    """Initialize all available characters"""
    char_dir = Path(__file__).parent / "characters"

    for char_file in char_dir.glob("*.json"):
        character_name = char_file.stem
        try:
            characters[character_name] = load_character(character_name)
            logger.info(f"Loaded character: {character_name}")
        except Exception as e:
            logger.error(f"Failed to load character {character_name}: {e}")


def get_scene_context(user_id: int) -> dict:
    """유저의 현재 세션 장면 컨텍스트 반환"""
    if user_id not in _scene_context:
        _scene_context[user_id] = {
            'in_scene': False,
            'scene_desc': '',
            'consent_streak': 0,
        }
    return _scene_context[user_id]


def update_scene_context(user_id: int, arousal: int, user_text: str):
    """arousal과 메시지 기반으로 세션 컨텍스트 업데이트"""
    ctx = get_scene_context(user_id)
    stripped = user_text.strip().lower().replace(' ', '')

    if arousal >= 41:
        ctx['in_scene'] = True

    if arousal < 20:
        ctx['in_scene'] = False
        ctx['scene_desc'] = ''
        ctx['consent_streak'] = 0

    # 단순 동의 연속 카운트
    if stripped in CONSENT_PATTERNS:
        ctx['consent_streak'] += 1
    else:
        ctx['consent_streak'] = 0

    # 신음만 보낸 경우도 장면 진행
    if stripped in USER_MOAN_PATTERNS:
        ctx['in_scene'] = True


def is_user_moan_only(text: str) -> bool:
    """유저가 신음 표현만 보냈는지 확인"""
    stripped = text.strip().lower().replace(' ', '')
    return stripped in USER_MOAN_PATTERNS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    # Get or create user
    user = db.get_or_create_user(user_id, username=username)

    # Age verification notice (NSFW mode)
    if config.get('nsfw_mode') and config.get('age_verification'):
        age_notice = (
            "⚠️ 성인 전용 서비스입니다.\n"
            "이 봇을 이용하려면 만 18세 이상이어야 합니다.\n"
            "계속 이용하면 성인임에 동의하는 것으로 간주됩니다.\n\n"
        )
    else:
        age_notice = ""

    # Load default character
    character_name = user.get('character') or config.get('default_character', 'hana')
    character = characters.get(character_name)

    if not character:
        await update.message.reply_text(
            "안녕! 하지만 캐릭터를 불러올 수 없어. 관리자한테 문의해줘."
        )
        return

    # Create welcome message
    greeting = character.get('greeting', '안녕, 난 하나야!')

    welcome_msg = age_notice
    welcome_msg += f"{greeting}\n\n"
    welcome_msg += "명령어:\n"
    welcome_msg += "/reset - 대화 초기화\n"
    welcome_msg += "/character - 캐릭터 정보\n"
    welcome_msg += "/switch [이름] - 캐릭터 변경\n"
    welcome_msg += "/help - 도움말\n\n"
    welcome_msg += "편하게 말해 ♡"

    await update.message.reply_text(welcome_msg)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reset command"""
    user_id = update.effective_user.id
    db.reset_conversation(user_id)
    # 세션 컨텍스트도 초기화
    _scene_context.pop(user_id, None)

    await update.message.reply_text(
        "대화 기록 초기화했어. 처음부터 다시 시작할게 ♡"
    )


async def character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /character command"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    profile = db.get_user_profile(user_id)

    if not user:
        await update.message.reply_text("먼저 /start 써줘.")
        return

    character_name = user.get('character') or config.get('default_character', 'hana')
    char_data = characters.get(character_name)

    if not char_data:
        await update.message.reply_text("캐릭터 정보를 불러올 수 없어.")
        return

    info_msg = f"지금 캐릭터: {char_data['name']} ({char_data['name_en']})\n"
    info_msg += f"성격: {char_data['personality']}\n"
    info_msg += f"소개: {char_data.get('description', '')}\n\n"
    info_msg += f"함께한 날: {profile.get('days_together', 0)}일\n"
    info_msg += f"현재 기분: {profile.get('mood', 'normal')}\n\n"
    info_msg += "캐릭터 변경: /switch hana 또는 /switch naomi"

    await update.message.reply_text(info_msg)


async def switch_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /switch command"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("먼저 /start 써줘.")
        return

    if not context.args:
        available = ", ".join(characters.keys())
        await update.message.reply_text(
            f"사용법: /switch [캐릭터 이름]\n가능한 캐릭터: {available}"
        )
        return

    target = context.args[0].lower()
    if target not in characters:
        available = ", ".join(characters.keys())
        await update.message.reply_text(
            f"'{target}' 캐릭터 없어.\n가능한 캐릭터: {available}"
        )
        return

    db.update_character(user_id, target)
    db.reset_conversation(user_id)
    _scene_context.pop(user_id, None)

    char_data = characters[target]
    greeting = char_data.get('greeting', f'안녕, 나 {char_data["name"]}이야!')
    await update.message.reply_text(
        f"{char_data['name']}(으)로 바꿨어. 대화도 새로 시작!\n\n{greeting}"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_msg = "AI 여자친구 봇 사용법\n\n"
    help_msg += "/start - 봇 시작\n"
    help_msg += "/reset - 대화 초기화\n"
    help_msg += "/character - 캐릭터 정보\n"
    help_msg += "/help - 이 메시지\n\n"
    help_msg += "일반 메시지를 보내면 자연스럽게 대화해!"

    await update.message.reply_text(help_msg)


# ──────────────────────────────────────────────
# 2주차: 자동 요약
# ──────────────────────────────────────────────

async def auto_summarize(user_id: int, character_name: str):
    """대화 50턴 초과 시 LLM으로 핵심 요약 → DB 저장 → 오래된 메시지 삭제"""
    try:
        messages = db.get_recent_messages(user_id, 50)
        if not messages:
            return

        conv_text = "\n".join(
            f"{'사용자' if m['role'] == 'user' else '하나'}: {m['content']}"
            for m in messages
        )
        summary_system = (
            "다음 대화를 3줄 이내로 핵심만 요약해줘. "
            "사용자 이름, 중요한 감정, 언급된 취향/계획 위주로. "
            "반드시 한국어로, 간결하게."
        )
        summary_messages = [{"role": "user", "content": conv_text}]

        summary = await ollama_client.chat(
            summary_messages,
            system_prompt=summary_system,
            temperature=0.3,
            top_p=0.9
        )
        summary = OllamaClient.strip_thinking(summary)

        if summary:
            db.update_summary(user_id, summary)
            db.archive_old_messages(user_id, keep_count=10)
            logger.info(f"Auto-summarized conversation for user {user_id}")

    except Exception as e:
        logger.error(f"Auto-summarize failed for user {user_id}: {e}")


# ──────────────────────────────────────────────
# 2주차: 스케줄러
# ──────────────────────────────────────────────

async def send_morning_greeting(context):
    """매일 아침 8시"""
    all_users = db.get_all_users()
    for user in all_users:
        user_id = user['user_id']
        character_name = user.get('character') or config.get('default_character', 'hana')
        char_data = characters.get(character_name)
        if not char_data:
            continue
        greeting = char_data.get('sample_responses', {}).get('greeting_morning', '좋은 아침~')
        try:
            await context.bot.send_message(chat_id=user_id, text=greeting)
        except Exception as e:
            logger.warning(f"Morning greeting failed for {user_id}: {e}")


async def send_night_greeting(context):
    """매일 밤 11시"""
    all_users = db.get_all_users()
    for user in all_users:
        user_id = user['user_id']
        character_name = user.get('character') or config.get('default_character', 'hana')
        char_data = characters.get(character_name)
        if not char_data:
            continue
        greeting = char_data.get('sample_responses', {}).get('greeting_night', '오늘 하루 수고했어. 잘 자~')
        try:
            await context.bot.send_message(chat_id=user_id, text=greeting)
        except Exception as e:
            logger.warning(f"Night greeting failed for {user_id}: {e}")


async def update_all_days_together(context):
    """매일 자정"""
    all_users = db.get_all_users()
    for user in all_users:
        try:
            db.increment_days_together(user['user_id'])
        except Exception as e:
            logger.warning(f"Days together update failed for {user['user_id']}: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages"""
    user_id = update.effective_user.id
    user_text = update.message.text
    username = update.effective_user.first_name

    # Check user exists
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("먼저 /start 써줘.")
        return

    db.update_last_seen(user_id)
    db.save_message(user_id, "user", user_text)

    # ── 감정 감지 ──
    detected_mood, mood_conf = detect_emotion(user_text)
    if mood_conf >= 0.5 and detected_mood != 'normal':
        db.update_mood(user_id, detected_mood)

    # ── 취향 추출 ──
    new_prefs = extract_preferences(user_text)
    if new_prefs:
        db.update_preferences(user_id, new_prefs)

    # ── 흥분도 + 호감도 ──
    gauge = db.get_arousal_affection(user_id)
    current_arousal = gauge['arousal']
    current_affection = gauge['affection']

    affection_delta = calculate_affection_delta(user_text)
    new_affection = max(0, min(100, current_affection + affection_delta))
    if affection_delta != 0:
        db.update_affection(user_id, new_affection)

    arousal_delta = calculate_arousal_delta(user_text, new_affection)

    # ── 단순 동의("응") 처리 — arousal decay 방지 ──
    stripped_text = user_text.strip().lower().replace(' ', '')
    is_moan_only = is_user_moan_only(user_text)
    is_consent = stripped_text in CONSENT_PATTERNS

    if arousal_delta == 0 and current_arousal > 0:
        if is_consent or is_moan_only:
            # 동의/신음 → decay 없이 현재 상태 유지
            arousal_delta = 0
        elif current_arousal >= 80:
            arousal_delta = -8
        elif current_arousal >= 50:
            arousal_delta = -5
        else:
            arousal_delta = -2

    new_arousal = max(0, current_arousal + arousal_delta)

    # 오르가즘 체크
    orgasm_triggered = check_orgasm(new_arousal)
    if orgasm_triggered:
        new_arousal = 30
    db.update_arousal(user_id, new_arousal)
    logger.debug(
        f"Arousal: {current_arousal}→{new_arousal} (Δ{arousal_delta}), "
        f"Affection: {current_affection}→{new_affection}, "
        f"Orgasm: {orgasm_triggered}, Consent: {is_consent}, Moan: {is_moan_only}"
    )

    # ── 세션 컨텍스트 업데이트 ──
    update_scene_context(user_id, new_arousal, user_text)
    scene_ctx = get_scene_context(user_id)

    # Check for image request
    if any(kw in user_text for kw in ["사진", "사진 보내", "사진 줘", "그림", "셀카", "사진 찍어"]):
        await update.message.reply_text(
            "사진 기능은 곧 추가될 예정이야! (ComfyUI 연동 준비 중) ♡"
        )
        return

    # Get character and recent messages
    character_name = user.get('character') or config.get('default_character', 'hana')
    character = characters.get(character_name)
    profile = db.get_user_profile(user_id)

    if not character:
        await update.message.reply_text("캐릭터를 불러올 수 없어.")
        return

    messages = db.get_recent_messages(user_id, config.get('max_history', 50))

    # Check Ollama availability
    ollama_available = await ollama_client.is_available()
    if not ollama_available:
        model_name = config.get('model', 'huihui_ai/qwen3.5-abliterated:35b')
        await update.message.reply_text(
            f"Ollama 서버가 꺼져있어. 확인해줘:\n"
            f"1. Ollama 앱 실행했어?\n"
            f"2. 모델 다운됐어? → ollama pull {model_name}"
        )
        return

    await update.message.chat.send_action("typing")

    # ── 시스템 프롬프트 구성 ──
    system_prompt = character.get('system_prompt', '')

    if username:
        system_prompt += f"\n\n[사용자 정보]\n- 이름/닉네임: {username}\n"

    mood = profile.get('mood', 'normal')
    if mood != 'normal':
        system_prompt += f"- 현재 기분: {mood}\n"

    system_prompt += f"- 함께한 날: {profile.get('days_together', 0)}일\n"

    if profile.get('summary'):
        system_prompt += f"\n[이전 대화 핵심 요약]\n{profile['summary']}\n"

    prefs = profile.get('preferences', {})
    if prefs:
        pref_str = ', '.join(prefs.values())
        system_prompt += f"- 유저 취향/관심사: {pref_str}\n"

    # ── 흥분도 / 호감도 상태 주입 ──
    arousal_state = get_arousal_state(100 if orgasm_triggered else new_arousal)
    system_prompt += (
        f"\n[현재 하나의 내면 상태]\n"
        f"- 호감도: {new_affection}/100\n"
        f"- 흥분도: {new_arousal}/100 ({arousal_state['label']})\n"
        f"- 지금 이 상태로 반응해: {arousal_state['instruction']}\n"
    )
    if orgasm_triggered:
        system_prompt += (
            "- ⚠️ 지금 막 오르가즘을 느꼈어. 이번 한 번만 절정 반응을 표현해. "
            "끄으응... 으으응... 몸이 떨리고 말이 안 나오는 상태야. 황홀하고 지쳐.\n"
        )

    # ── 장면 컨텍스트 힌트 주입 ──
    if scene_ctx['in_scene'] and scene_ctx['consent_streak'] >= 1:
        system_prompt += (
            f"\n[장면 진행 힌트]\n"
            f"- 유저가 '{user_text.strip()}'라고만 했어. 이건 지금 장면을 계속하라는 동의야.\n"
            f"- 이전 장면에서 이어서 더 구체적인 신체 묘사나 신음을 표현해.\n"
            f"- '좋아', '응', '알겠어' 같은 반복 단답 절대 금지. 장면을 앞으로 진행시켜.\n"
        )

    if is_moan_only:
        system_prompt += (
            f"\n[유저 신음 감지]\n"
            f"- 유저가 '{user_text.strip()}' 라고 했어. 이건 유저가 흥분했다는 신호야.\n"
            f"- 절대 따라하지 마. 네가 그 신음에 더 흥분해서 몸이 반응하는 묘사를 해.\n"
            f"- 예: '으음... 그렇게 소리내면 나도 더 흥분돼' 또는 몸 상태 직접 묘사.\n"
        )

    # ── 현재 시각 주입 ──
    now = datetime.now()
    weekday_ko = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][now.weekday()]
    system_prompt += (
        f"\n[현재 시각]\n"
        f"{now.year}년 {now.month}월 {now.day}일 {weekday_ko} "
        f"{now.hour}시 {now.minute:02d}분\n"
        f"절대 시간을 추측하거나 지어내지 마.\n"
    )

    # ── Few-shot 프라이밍 삽입 ──
    # 실제 대화 history 앞에 좋은 예시 대화를 끼워 넣어서
    # 모델이 올바른 응답 패턴을 바로 학습하게 만듦
    priming = get_priming_examples(new_arousal)
    real_messages = [
        {"role": msg['role'], "content": msg['content']}
        for msg in messages
    ]
    # 프라이밍 + 실제 대화 순서로 결합
    api_messages = priming + real_messages
    logger.debug(f"Priming: {len(priming)} examples injected (arousal={new_arousal})")

    response_text = ""
    try:
        async for chunk in ollama_client.chat_stream(
            api_messages,
            system_prompt=system_prompt,
            temperature=config.get('temperature', 0.9),
            top_p=config.get('top_p', 0.92)
        ):
            response_text += chunk

        response_text = ollama_client.strip_thinking(response_text)

        # 줄바꿈 정리
        lines = [line.strip() for line in response_text.splitlines() if line.strip()]
        response_text = ' '.join(lines)

        import re

        # ── Post-processing 1: 보이지 않는 Unicode 제어문자 제거 ──
        # zero-width space, BOM, soft hyphen 등 invisible char
        response_text = re.sub(r'[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad]', '', response_text)

        # ── Post-processing 2: ASCII art / 쓰레기 반복 패턴 제거 ──
        # ===, ---, ***, ███ 같은 패턴만 타깃팅 (한국어 건드리지 않음)
        response_text = re.sub(r'[=\-*#_|]{3,}', '', response_text)        # === --- ***
        response_text = re.sub(r'[█▀▄▌▐░▒▓]{2,}', '', response_text)       # block chars
        response_text = re.sub(r'[┌┐└┘│─┼├┤┬┴]{2,}', '', response_text)   # box drawing

        # ── Post-processing 3: 이모지 폭발 제거 ──
        # 이모지 4개 이상이면 전부 제거 (1~3개는 허용 — ♡ 등 보존)
        emoji_pat = re.compile(
            "["
            "\U0001F600-\U0001F64F"   # 감정
            "\U0001F300-\U0001F5FF"   # 기호/지도
            "\U0001F680-\U0001F6FF"   # 교통
            "\U0001F900-\U0001F9FF"   # 보충
            "\U0001FA00-\U0001FAFF"   # 추가
            "]+", flags=re.UNICODE
        )
        emoji_count = len(emoji_pat.findall(response_text))
        if emoji_count >= 4:
            response_text = emoji_pat.sub('', response_text)
            logger.warning(f"Emoji explosion ({emoji_count}) cleaned for user {user_id}")

        # ── Post-processing 4: 단독 마침표 제거 (... 은 보존) ──
        # 패턴: 마침표가 1개짜리로 끝나는 경우만 제거
        response_text = re.sub(r'(?<!\.)\.(?!\.)', ' ', response_text)

        # ── Post-processing 5: 연속 공백 정리 ──
        response_text = re.sub(r' {2,}', ' ', response_text).strip()

        # ── Post-processing 6: 유저 텍스트 미러링 감지 ──
        user_stripped = user_text.strip()
        if len(user_stripped) >= 2 and response_text.startswith(user_stripped):
            response_text = response_text[len(user_stripped):].strip()
            if not response_text:
                response_text = "으음... 나도"
            logger.warning(f"Mirroring trimmed for user {user_id}")

        # 빈 응답 방어
        if not response_text.strip():
            logger.warning("Empty response from Ollama")
            response_text = "..."

        db.save_message(user_id, "assistant", response_text)

        # 자동 요약
        msg_count = db.get_conversation_count(user_id)
        if msg_count >= 50:
            asyncio.create_task(auto_summarize(user_id, character_name))

        if len(response_text) > 4096:
            for i in range(0, len(response_text), 4096):
                await update.message.reply_text(response_text[i:i+4096])
        else:
            await update.message.reply_text(response_text)

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        await update.message.reply_text(f"응답 생성 중 오류: {str(e)}")


async def set_commands(application: Application):
    """Set bot commands"""
    commands = [
        BotCommand("start", "봇 시작하기"),
        BotCommand("reset", "대화 초기화"),
        BotCommand("character", "캐릭터 정보"),
        BotCommand("switch", "캐릭터 변경"),
        BotCommand("help", "도움말"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    """Main entry point"""
    global db, ollama_client, config

    config = load_config()

    if config.get('telegram_token') == 'YOUR_BOT_TOKEN_HERE':
        print("ERROR: Please set your Telegram bot token in config.json")
        sys.exit(1)

    db = Database("gf_bot.db")
    logger.info("Database initialized")

    ollama_client = OllamaClient(
        base_url=config.get('ollama_url', 'http://localhost:11434'),
        model=config.get('model', 'huihui_ai/qwen3.5-abliterated:35b'),
        keep_alive=config.get('keep_alive', '10m')
    )
    logger.info(f"Ollama client initialized: {config.get('model')}")

    init_characters()

    if not characters:
        print("WARNING: No characters loaded. Check characters/ directory")

    application = Application.builder().token(config.get('telegram_token')).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("character", character))
    application.add_handler(CommandHandler("switch", switch_character))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.post_init = set_commands

    # 스케줄러 (KST = UTC+9)
    KST = timezone(timedelta(hours=9))
    job_queue = application.job_queue

    job_queue.run_daily(send_morning_greeting, time=dtime(8, 0, 0, tzinfo=KST), name="morning_greeting")
    job_queue.run_daily(send_night_greeting, time=dtime(23, 0, 0, tzinfo=KST), name="night_greeting")
    job_queue.run_daily(update_all_days_together, time=dtime(0, 0, 0, tzinfo=KST), name="days_together")
    logger.info("Schedulers registered: morning(08:00 KST), night(23:00 KST), midnight(00:00 KST)")

    logger.info("Starting bot...")
    print("Bot started. Press Ctrl+C to stop.")

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("Bot stopped.")


if __name__ == '__main__':
    main()
