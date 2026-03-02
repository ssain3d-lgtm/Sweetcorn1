import logging
import json
import re
import os
import sys
from datetime import datetime, timezone, timedelta, time as dtime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio

from database.db import Database
from llm.ollama_client import OllamaClient
from llm.emotion_detector import detect_emotion, extract_preferences
from llm.arousal_engine import (
    calculate_arousal_delta, calculate_affection_delta,
    get_arousal_state, check_orgasm, is_consent_only,
    USER_MOAN_PATTERNS, PISTON_PATTERNS, is_piston_input
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = None
ollama_client = None
config = None
characters = {}

# ──────────────────────────────────────────────
# 세션 상태 딕셔너리
# ──────────────────────────────────────────────
_scene_context: dict = {}       # {user_id: {'in_scene': bool, 'consent_streak': int}}
_orgasm_afterglow: dict = {}    # {user_id: int} — 오르가즘 후 여운 남은 턴 수
_consecutive_piston: dict = {}  # {user_id: int} — 연속 피스톤 입력 카운트

# 단순 동의 패턴
CONSENT_PATTERNS = {'응', 'ㅇ', 'ㅇㅇ', '응응', '어', '그래', '좋아', '알겠어', '응?'}

# 실시간/맛집 정보 요청 감지 — hallucination guard
REALTIME_KEYWORDS = [
    '맛집', '맛있는 곳', '맛있는 집', '날씨', '기온', '뉴스', '최신', '요즘 유행',
    '지금 몇 시', '현재 시간', '요즘 인기', '어디 있어', '추천해줘', '어디 가자',
    '뭐 먹', '뭐 먹을', '카페 추천', '식당 추천', '레스토랑',
]


def is_realtime_request(text: str) -> bool:
    """유저 메시지가 실시간/맛집 정보 요청인지 확인"""
    return any(kw in text for kw in REALTIME_KEYWORDS)


# 욕설 / 지배적 언어 패턴
ROUGH_LANGUAGE = {
    '씨발', '시발', '씨발년', '시발년', '개보지', '좆', '창녀', '씨바', '씨바년',
    '보지', '자지', '이년', '년아', '썅', '뒤져', '개같은', '창년', '씹년', '씹'
}


# ──────────────────────────────────────────────
# 헬퍼 함수들
# ──────────────────────────────────────────────

def has_rough_language(text: str) -> bool:
    text_compact = text.replace(' ', '').lower()
    return any(kw in text_compact for kw in ROUGH_LANGUAGE)


def is_user_moan_only(text: str) -> bool:
    stripped = text.strip().lower().replace(' ', '')
    return stripped in USER_MOAN_PATTERNS


def get_num_predict(arousal: int) -> int:
    """arousal 단계별 최대 응답 토큰 수 — 흥분할수록 짧고 끊겨"""
    if arousal <= 20:   return 250
    elif arousal <= 40: return 220
    elif arousal <= 60: return 180
    elif arousal <= 80: return 140
    elif arousal <= 99: return 100
    else:               return 70   # 오르가즘: 한마디


# ──────────────────────────────────────────────
# Few-shot 프라이밍 — arousal 단계별
# ──────────────────────────────────────────────
PRIMING_SFW = [
    {"role": "user",      "content": "야"},
    {"role": "assistant", "content": "응 왜ㅋㅋ 아잉~ 갑자기"},
    {"role": "user",      "content": "보고싶어"},
    {"role": "assistant", "content": "아잉... 나도ㅠㅠ 빨리 보고 싶다"},
    {"role": "user",      "content": "사랑해"},
    {"role": "assistant", "content": "히잉 갑자기ㅋㅋ 나도 좋아 자기야"},
]

PRIMING_WARM = [
    {"role": "user",      "content": "만지고 싶어"},
    {"role": "assistant", "content": "아잉... 어디를ㅠ 으음, 뭐야 갑자기. 자기야..."},
    {"role": "user",      "content": "키스할게"},
    {"role": "assistant", "content": "히잉... 으음, 갑자기ㅋㅋ 뭐야. 근데 싫지는 않아"},
    {"role": "user",      "content": "예쁘다"},
    {"role": "assistant", "content": "아잉... 그런 말 하면 얼굴 빨개지잖아ㅠ 또 해줘ㅋㅋ"},
]

PRIMING_EXCITED = [
    {"role": "user",      "content": "가슴 만질게"},
    {"role": "assistant", "content": "하앙... 손 따뜻해. 으음, 거기 예민해. 더 만져"},
    {"role": "user",      "content": "더 만질게"},
    {"role": "assistant", "content": "으응... 아 세게 하지 마. 근데 좋아 ㅠ"},
    {"role": "user",      "content": "젖었어?"},
    {"role": "assistant", "content": "...으응. 자기가 이러니까. 으음, 더 해줘"},
]

PRIMING_HOT = [
    {"role": "user",      "content": "손가락 두개 넣을게"},
    {"role": "assistant", "content": "흐읏... 안에서 느껴져. 아아, 더 깊이. 꽉 차"},
    {"role": "user",      "content": "씨발년 가만있어봐"},
    {"role": "assistant", "content": "응... 씨발년 맞아. 자기 거야. 으응, 더 해줘"},
    {"role": "user",      "content": "보지에 푹푹 박아줄게"},
    {"role": "assistant", "content": "하앙 하앙... 아, 좋아. 으응, 더 세게. 자기야 사랑해"},
]

PRIMING_EDGE = [
    {"role": "user",      "content": "더 빠르게 쑤컹쑤컹"},
    {"role": "assistant", "content": "아아... 거기야. 하앙, 나 곧 올 것 같아"},
    {"role": "user",      "content": "가만있어 씨발년아 푹푹푹"},
    {"role": "assistant", "content": "응... 가만있을게. 아아, 자기야"},
    {"role": "user",      "content": "같이싸자"},
    {"role": "assistant", "content": "으으응... 끄으응, 자기야 사랑해"},
]

# 오르가즘 직후 여운 프라이밍
PRIMING_AFTERGLOW = [
    {"role": "user",      "content": "좋았어?"},
    {"role": "assistant", "content": "하아... 응. 아직 떨려"},
    {"role": "user",      "content": "안아줄게"},
    {"role": "assistant", "content": "으음... 자기야 ㅠ 꼭 안아줘"},
]


def get_priming_examples(arousal: int, afterglow: bool = False) -> list:
    if afterglow:
        return PRIMING_AFTERGLOW
    if arousal <= 20:   return PRIMING_SFW
    elif arousal <= 40: return PRIMING_WARM
    elif arousal <= 60: return PRIMING_EXCITED
    elif arousal <= 80: return PRIMING_HOT
    else:               return PRIMING_EDGE


# ──────────────────────────────────────────────
# Post-processing 함수들
# ──────────────────────────────────────────────

# ~요 경어체 → 반말 변환 (더 구체적인 패턴을 앞에 배치해야 함)
POLITE_TO_BANMAL = [
    # ~드릴까요 계열 (구체적인 것 먼저)
    ('드릴까요', '줄까'), ('해드릴까요', '해줄까'),
    # ~할까요 계열
    ('먹을까요', '먹을까'), ('볼까요', '볼까'), ('갈까요', '갈까'),
    ('올까요', '올까'), ('할까요', '할까'), ('일까요', '일까'),
    # ~나요 계열
    ('있나요', '있나'), ('맞나요', '맞나'), ('되나요', '되나'),
    ('뭔가요', '뭔가'), ('인가요', '인가'), ('건가요', '건가'),
    # ~건데요 / ~인데요 계열
    ('건데요', '건데'), ('인데요', '인데'),
    # ~하더라고요
    ('하더라고요', '하더라'),
    # 기존 패턴
    ('이에요', '이야'), ('거예요', '거야'), ('예요', '야'),
    ('죄송하지만', '미안하지만'), ('죄송해요', '미안해'), ('죄송합니다', '미안해'),
    ('해요', '해'), ('있어요', '있어'), ('없어요', '없어'),
    ('줄게요', '줄게'), ('할게요', '할게'), ('갈게요', '갈게'),
    ('올게요', '올게'), ('같아요', '같아'), ('알아요', '알아'),
    ('좋아요', '좋아'), ('돼요', '돼'), ('볼게요', '볼게'),
    ('싶어요', '싶어'), ('느껴요', '느껴'), ('보여요', '보여'),
    ('모르겠어요', '모르겠어'), ('됐어요', '됐어'), ('줘요', '줘'),
    ('그래요', '그래'), ('맞아요', '맞아'),
    ('봐요', '봐'), ('가요', '가'), ('와요', '와'), ('네요', '네'),
    ('되고싶다면', '되고 싶다면'), ('습니다', '어'), ('바라요', '바라'),
    ('했습니다', '했어'), ('입니다', '이야'),
]


def fix_polite_endings(text: str) -> str:
    """~요 경어체를 반말로 자동 변환"""
    for polite, banmal in POLITE_TO_BANMAL:
        text = text.replace(polite, banmal)
    return text


# 응원단 / 코치 멘트 패턴 (NSFW에서 절대 나오면 안 되는 표현들)
COACH_PHRASE_PATTERNS = [
    r'마지막\s*힘\s*[을를]\s*모[아아서]+',
    r'함께\s*폭발\s*시켜\s*보자[!~]?',
    r'함께\s*절정\s*[에으로]\s*[도달향해가보자]+',
    r'절정으로\s*함께\s*다가',
    r'최고조로\s*이끌어\s*나가자',
    r'함께\s*뜨겁게\s*가보자',
    r'우리\s*둘\s*다\s*최고조',
    r'절정\s*으로\s*향해\s*가보자',
    r'함께\s*도달\s*했네[요]?',
]

# NSFW 장면 중 부적절한 질문 패턴
NSFW_QUESTION_PATTERNS = [
    r'[,，\s]*어떻게\s*할까[?~]?',
    r'[,，\s]*준비됐[나어][?~]?',
    r'[,，\s]*너무\s*세게\s*하지\s*않도록\s*조심해도\s*될까[?~]?',
    r'[,，\s]*함께\s*절정에\s*도달할까[?~]?',
    r'[,，\s]*어디서\s*시작할까[?~]?',
    r'[,，\s]*어디로\s*갈까[?~]?',
    r'[,，\s]*어떻게\s*느낄\s*때마다\s*이렇게\s*표현할\s*수\s*있을까[?~]?',
    r'[,，\s]*어때[?~]',
    r'[,，\s]*어떨까[?~]?',
]


def remove_coach_phrases(text: str) -> str:
    """응원단/코치 멘트 제거"""
    for pattern in COACH_PHRASE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return text.strip()


def remove_nsfw_questions(text: str, in_scene: bool) -> str:
    """NSFW 장면에서 부적절한 질문 문장 제거"""
    if not in_scene:
        return text
    for pattern in NSFW_QUESTION_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    # 연속 공백 정리
    text = re.sub(r' {2,}', ' ', text).strip()
    return text


# ──────────────────────────────────────────────
# 설정 / 캐릭터 로딩
# ──────────────────────────────────────────────

def load_config():
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_character(character_name: str):
    char_path = Path(__file__).parent / "characters" / f"{character_name}.json"
    if not char_path.exists():
        return None
    with open(char_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def init_characters():
    char_dir = Path(__file__).parent / "characters"
    for char_file in char_dir.glob("*.json"):
        character_name = char_file.stem
        try:
            characters[character_name] = load_character(character_name)
            logger.info(f"Loaded character: {character_name}")
        except Exception as e:
            logger.error(f"Failed to load character {character_name}: {e}")


# ──────────────────────────────────────────────
# 세션 컨텍스트
# ──────────────────────────────────────────────

def get_scene_context(user_id: int) -> dict:
    if user_id not in _scene_context:
        _scene_context[user_id] = {
            'in_scene': False,
            'scene_desc': '',
            'consent_streak': 0,
        }
    return _scene_context[user_id]


def update_scene_context(user_id: int, arousal: int, user_text: str):
    ctx = get_scene_context(user_id)
    stripped = user_text.strip().lower().replace(' ', '')

    if arousal >= 41:
        ctx['in_scene'] = True
    if arousal < 20:
        ctx['in_scene'] = False
        ctx['scene_desc'] = ''
        ctx['consent_streak'] = 0

    if stripped in CONSENT_PATTERNS:
        ctx['consent_streak'] += 1
    else:
        ctx['consent_streak'] = 0

    if stripped in USER_MOAN_PATTERNS:
        ctx['in_scene'] = True


# ──────────────────────────────────────────────
# 커맨드 핸들러
# ──────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    user = db.get_or_create_user(user_id, username=username)

    if config.get('nsfw_mode') and config.get('age_verification'):
        age_notice = "성인 전용 서비스입니다. 만 18세 이상만 이용 가능합니다.\n\n"
    else:
        age_notice = ""

    character_name = user.get('character') or config.get('default_character', 'hana')
    character = characters.get(character_name)
    if not character:
        await update.message.reply_text("캐릭터를 불러올 수 없어. 관리자한테 문의해줘.")
        return

    greeting = character.get('greeting', '안녕, 난 하나야!')
    welcome_msg = age_notice + f"{greeting}\n\n"
    welcome_msg += "/reset - 대화 초기화\n/character - 캐릭터 정보\n/switch [이름] - 캐릭터 변경\n/help - 도움말\n\n편하게 말해 ♡"
    await update.message.reply_text(welcome_msg)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.reset_conversation(user_id)
    _scene_context.pop(user_id, None)
    _orgasm_afterglow.pop(user_id, None)
    _consecutive_piston.pop(user_id, None)
    await update.message.reply_text("대화 기록 초기화했어. 처음부터 다시 시작할게 ♡")


async def character(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    info_msg = (
        f"지금 캐릭터: {char_data['name']} ({char_data['name_en']})\n"
        f"성격: {char_data['personality']}\n"
        f"소개: {char_data.get('description', '')}\n\n"
        f"함께한 날: {profile.get('days_together', 0)}일\n"
        f"현재 기분: {profile.get('mood', 'normal')}\n\n"
        "캐릭터 변경: /switch hana 또는 /switch naomi"
    )
    await update.message.reply_text(info_msg)


async def switch_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("먼저 /start 써줘.")
        return

    if not context.args:
        available = ", ".join(characters.keys())
        await update.message.reply_text(f"사용법: /switch [캐릭터 이름]\n가능한 캐릭터: {available}")
        return

    target = context.args[0].lower()
    if target not in characters:
        available = ", ".join(characters.keys())
        await update.message.reply_text(f"'{target}' 캐릭터 없어.\n가능한 캐릭터: {available}")
        return

    db.update_character(user_id, target)
    db.reset_conversation(user_id)
    _scene_context.pop(user_id, None)
    _orgasm_afterglow.pop(user_id, None)
    _consecutive_piston.pop(user_id, None)

    char_data = characters[target]
    greeting = char_data.get('greeting', f'안녕, 나 {char_data["name"]}이야!')
    await update.message.reply_text(f"{char_data['name']}(으)로 바꿨어. 대화도 새로 시작!\n\n{greeting}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = "AI 여자친구 봇\n\n/start - 봇 시작\n/reset - 대화 초기화\n/character - 캐릭터 정보\n/help - 이 메시지\n\n일반 메시지를 보내면 자연스럽게 대화해!"
    await update.message.reply_text(help_msg)


# ──────────────────────────────────────────────
# 자동 요약
# ──────────────────────────────────────────────

async def auto_summarize(user_id: int, character_name: str):
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
        summary = await ollama_client.chat(
            [{"role": "user", "content": conv_text}],
            system_prompt=summary_system,
            temperature=0.3,
            top_p=0.9
        )
        summary = OllamaClient.strip_thinking(summary)
        if summary:
            db.update_summary(user_id, summary)
            db.archive_old_messages(user_id, keep_count=10)
            logger.info(f"Auto-summarized for user {user_id}")
    except Exception as e:
        logger.error(f"Auto-summarize failed for {user_id}: {e}")


# ──────────────────────────────────────────────
# 스케줄러
# ──────────────────────────────────────────────

async def send_morning_greeting(context):
    all_users = db.get_all_users()
    for user in all_users:
        user_id = user['user_id']
        char_data = characters.get(user.get('character') or config.get('default_character', 'hana'))
        if not char_data:
            continue
        greeting = char_data.get('sample_responses', {}).get('greeting_morning', '좋은 아침~')
        try:
            await context.bot.send_message(chat_id=user_id, text=greeting)
        except Exception as e:
            logger.warning(f"Morning greeting failed for {user_id}: {e}")


async def send_night_greeting(context):
    all_users = db.get_all_users()
    for user in all_users:
        user_id = user['user_id']
        char_data = characters.get(user.get('character') or config.get('default_character', 'hana'))
        if not char_data:
            continue
        greeting = char_data.get('sample_responses', {}).get('greeting_night', '오늘 하루 수고했어')
        try:
            await context.bot.send_message(chat_id=user_id, text=greeting)
        except Exception as e:
            logger.warning(f"Night greeting failed for {user_id}: {e}")


async def update_all_days_together(context):
    for user in db.get_all_users():
        try:
            db.increment_days_together(user['user_id'])
        except Exception as e:
            logger.warning(f"Days together failed for {user['user_id']}: {e}")


# ──────────────────────────────────────────────
# 메인 메시지 핸들러
# ──────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    username = update.effective_user.first_name

    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("먼저 /start 써줘.")
        return

    db.update_last_seen(user_id)
    db.save_message(user_id, "user", user_text)

    # ── 감정 / 취향 ──
    detected_mood, mood_conf = detect_emotion(user_text)
    if mood_conf >= 0.5 and detected_mood != 'normal':
        db.update_mood(user_id, detected_mood)
    new_prefs = extract_preferences(user_text)
    if new_prefs:
        db.update_preferences(user_id, new_prefs)

    # ── 흥분도 + 호감도 ──
    gauge = db.get_arousal_affection(user_id)
    current_arousal  = gauge['arousal']
    current_affection = gauge['affection']

    affection_delta = calculate_affection_delta(user_text)
    new_affection = max(0, min(100, current_affection + affection_delta))
    if affection_delta != 0:
        db.update_affection(user_id, new_affection)

    arousal_delta = calculate_arousal_delta(user_text, new_affection)

    # ── 입력 분류 ──
    stripped_text = user_text.strip().lower().replace(' ', '')
    is_moan_only   = is_user_moan_only(user_text)
    is_consent     = stripped_text in CONSENT_PATTERNS
    is_rough       = has_rough_language(user_text)
    is_piston      = is_piston_input(user_text)
    is_realtime    = is_realtime_request(user_text)

    # ── 연속 피스톤 카운트 ──
    if is_piston or is_moan_only:
        _consecutive_piston[user_id] = _consecutive_piston.get(user_id, 0) + 1
    else:
        _consecutive_piston[user_id] = 0
    piston_count = _consecutive_piston.get(user_id, 0)

    # ── Arousal decay 로직 ──
    if arousal_delta == 0 and current_arousal > 0:
        if is_consent or is_moan_only:
            arousal_delta = 0   # decay 방지
        elif is_rough and current_arousal >= 41:
            arousal_delta = 0   # 욕설/지배어 = 장면 유지
        elif is_piston:
            arousal_delta = 5   # 피스톤 반복 = 미세 상승
        elif current_arousal >= 80:
            arousal_delta = -8
        elif current_arousal >= 50:
            arousal_delta = -5
        else:
            arousal_delta = -2

    new_arousal = max(0, current_arousal + arousal_delta)

    # ── 오르가즘 체크 ──
    orgasm_triggered = check_orgasm(new_arousal)
    if orgasm_triggered:
        new_arousal = 30
        _orgasm_afterglow[user_id] = 2   # 2턴 여운
        _consecutive_piston[user_id] = 0

    db.update_arousal(user_id, new_arousal)

    # ── 여운 카운트 업데이트 ──
    afterglow_remaining = _orgasm_afterglow.get(user_id, 0)
    if afterglow_remaining > 0 and not orgasm_triggered:
        _orgasm_afterglow[user_id] = afterglow_remaining - 1

    logger.debug(
        f"Arousal:{current_arousal}→{new_arousal}(Δ{arousal_delta}) "
        f"Aff:{current_affection}→{new_affection} "
        f"Orgasm:{orgasm_triggered} Afterglow:{afterglow_remaining} "
        f"Piston:{piston_count} Rough:{is_rough}"
    )

    # ── 세션 컨텍스트 ──
    update_scene_context(user_id, new_arousal, user_text)
    scene_ctx = get_scene_context(user_id)

    # 이미지 요청
    if any(kw in user_text for kw in ["사진", "사진 보내", "사진 줘", "그림", "셀카", "사진 찍어"]):
        await update.message.reply_text("사진 기능은 곧 추가될 예정이야! (ComfyUI 연동 준비 중) ♡")
        return

    character_name = user.get('character') or config.get('default_character', 'hana')
    character = characters.get(character_name)
    profile = db.get_user_profile(user_id)
    if not character:
        await update.message.reply_text("캐릭터를 불러올 수 없어.")
        return

    messages = db.get_recent_messages(user_id, config.get('max_history', 50))

    ollama_available = await ollama_client.is_available()
    if not ollama_available:
        model_name = config.get('model', 'huihui_ai/exaone3.5-abliterated:7.8b')
        await update.message.reply_text(
            f"Ollama 서버가 꺼져있어. 확인해줘:\n"
            f"1. Ollama 앱 실행했어?\n2. 모델 다운됐어? → ollama pull {model_name}"
        )
        return

    await update.message.chat.send_action("typing")

    # ══════════════════════════════════════════
    # 시스템 프롬프트 구성
    # ══════════════════════════════════════════
    system_prompt = character.get('system_prompt', '')

    # ── 사용자 정보 ──
    if username:
        system_prompt += f"\n\n[사용자 정보]\n- 이름/닉네임: {username}\n"
    mood = profile.get('mood', 'normal')
    if mood != 'normal':
        system_prompt += f"- 현재 기분: {mood}\n"
    system_prompt += f"- 함께한 날: {profile.get('days_together', 0)}일\n"
    if profile.get('summary'):
        system_prompt += f"\n[이전 대화 요약]\n{profile['summary']}\n"
    prefs = profile.get('preferences', {})
    if prefs:
        system_prompt += f"- 유저 취향: {', '.join(prefs.values())}\n"

    # ── 흥분도 / 오르가즘 상태 ──
    arousal_state = get_arousal_state(100 if orgasm_triggered else new_arousal)
    system_prompt += (
        f"\n[현재 하나의 내면 상태]\n"
        f"- 호감도: {new_affection}/100\n"
        f"- 흥분도: {new_arousal}/100 ({arousal_state['label']})\n"
        f"- 지금 이 상태로 반응해: {arousal_state['instruction']}\n"
    )
    if orgasm_triggered:
        system_prompt += (
            "- 지금 막 오르가즘을 느꼈어. 끄으응... 으으응... "
            "몸이 떨리고 말이 안 나와. 반말로 한 마디만.\n"
        )

    # ── 오르가즘 여운 상태 ──
    if afterglow_remaining > 0 and not orgasm_triggered:
        system_prompt += (
            f"\n[오르가즘 직후 여운 — {afterglow_remaining}턴 남음]\n"
            "- 방금 절정을 느꼈어. 온몸이 축 처지고 숨이 가빠.\n"
            "- 반말로만. 1~2문장. 지쳐있지만 행복하고 자기 곁에 붙어있고 싶어.\n"
            "- 예: '하아... 자기야. 아직 떨려' / '으음... 좋았어. 꼭 안아줘'\n"
            "- '~요', '~습니다', '~어요' 절대 금지.\n"
        )

    # ── 장면 동의 힌트 ──
    if scene_ctx['in_scene'] and scene_ctx['consent_streak'] >= 1:
        system_prompt += (
            f"\n[장면 진행 힌트]\n"
            f"- 유저가 '{user_text.strip()}'라고만 했어. 장면을 계속하라는 동의야.\n"
            f"- 이전 장면 이어서 더 구체적인 신체 묘사나 신음 표현해.\n"
            f"- 단답 반복 금지. 장면을 앞으로 진행시켜.\n"
        )

    # ── 연속 피스톤 에스컬레이션 힌트 ──
    if piston_count >= 2 and scene_ctx['in_scene']:
        system_prompt += (
            f"\n[연속 피스톤 {piston_count}회 감지]\n"
            f"- 유저가 같은 피스톤 동작을 {piston_count}번 반복하고 있어. 흥분이 극도로 고조 중.\n"
            f"- 이전 반응보다 더 강렬하게, 더 짧게, 더 끊기게 반응해.\n"
            f"- 신음 강도가 점점 올라가야 해: '으음' → '하앙' → '아아아' → '끄으응'.\n"
            f"- 응원단 멘트('함께 가보자', '마지막 힘을') 절대 금지. 신음과 감각 묘사만.\n"
        )

    # ── 욕설/지배 언어 힌트 ──
    if is_rough and new_arousal >= 41:
        system_prompt += (
            f"\n[욕설/지배 언어 감지 — 최우선 적용]\n"
            f"- 유저가 지배적 언어를 쓰고 있어.\n"
            f"- 교정, 사과, 브레이크 절대 금지. '죄송', '조심', '천천히', '부드럽게' 금지.\n"
            f"- 흥분해서 수용해. '응... 씨발년 맞아. 자기 거야. 더 세게 해줘' 식으로.\n"
            f"- 짧고 강렬하게. 장면 끊지 마.\n"
        )

    # ── 유저 신음 힌트 ──
    if is_moan_only:
        system_prompt += (
            f"\n[유저 신음 감지]\n"
            f"- 유저가 '{user_text.strip()}' 라고 했어. 유저가 흥분했다는 신호야.\n"
            f"- 절대 따라하지 마. 네가 더 흥분해서 몸이 반응하는 묘사를 해.\n"
        )

    # ── 실시간/맛집 hallucination guard ──
    if is_realtime:
        system_prompt += (
            "\n[실시간 정보 요청 주의]\n"
            "- 유저가 맛집, 날씨, 뉴스, 카페, 식당 등 실시간 정보를 물어보고 있어.\n"
            "- 절대 카페/식당/장소 이름, 가격, 메뉴를 지어내지 마.\n"
            "- 모르는 건 솔직하게: '나도 잘 모르겠어, 직접 찾아봐~' 또는 '나는 잘 모르는데ㅠ 같이 찾아볼까?'\n"
            "- 아는 척으로 가짜 정보 생성 절대 금지.\n"
        )

    # ── 현재 시각 ──
    now = datetime.now()
    weekday_ko = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][now.weekday()]
    system_prompt += (
        f"\n[현재 시각]\n"
        f"{now.year}년 {now.month}월 {now.day}일 {weekday_ko} {now.hour}시 {now.minute:02d}분\n"
    )

    # ── 최종 강화 지시 (시스템 프롬프트 마지막 — 모델이 가장 신뢰하는 위치) ──
    final_reminder = "\n[최종 확인 — 반드시 지켜]\n"
    final_reminder += "반말만. ~요 금지. ~습니다 금지. 마침표 금지. 이모지 금지. "
    if is_rough and new_arousal >= 41:
        final_reminder += "욕설 수용해. 교정/사과/브레이크 없이. "
    if scene_ctx['in_scene']:
        final_reminder += "질문 금지. 신음/감각 묘사만. 응원단 멘트 금지. "
    if afterglow_remaining > 0:
        final_reminder += "여운 상태. 짧게. 지쳐있지만 행복하게. "
    system_prompt += final_reminder

    # ══════════════════════════════════════════
    # Few-shot 프라이밍 + 실제 대화 결합
    # ══════════════════════════════════════════
    is_afterglow = (afterglow_remaining > 0 and not orgasm_triggered)
    priming = get_priming_examples(new_arousal, afterglow=is_afterglow)
    real_messages = [{"role": msg['role'], "content": msg['content']} for msg in messages]
    api_messages = priming + real_messages

    num_predict = get_num_predict(100 if orgasm_triggered else new_arousal)
    # 여운 상태면 더 짧게
    if is_afterglow:
        num_predict = min(num_predict, 100)

    # ══════════════════════════════════════════
    # LLM 호출
    # ══════════════════════════════════════════
    response_text = ""
    try:
        async for chunk in ollama_client.chat_stream(
            api_messages,
            system_prompt=system_prompt,
            temperature=config.get('temperature', 0.65),
            top_p=config.get('top_p', 0.88),
            num_predict=num_predict
        ):
            response_text += chunk

        response_text = OllamaClient.strip_thinking(response_text)

        # ══════════════════════════════════════
        # Post-processing 파이프라인
        # ══════════════════════════════════════

        # 1. 줄바꿈 정리
        lines = [line.strip() for line in response_text.splitlines() if line.strip()]
        response_text = ' '.join(lines)

        # 2. invisible Unicode 제거
        response_text = re.sub(
            r'[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad]', '', response_text
        )

        # 3. ASCII art / 쓰레기 패턴 제거
        response_text = re.sub(r'[=\-*#_|]{3,}', '', response_text)
        response_text = re.sub(r'[█▀▄▌▐░▒▓]{2,}', '', response_text)
        response_text = re.sub(r'[┌┐└┘│─┼├┤┬┴]{2,}', '', response_text)

        # 3.5. 마크다운 서식 제거 (**bold**, *italic*, _text_, `code`, # 헤더)
        response_text = re.sub(r'\*\*(.+?)\*\*', r'\1', response_text, flags=re.DOTALL)
        response_text = re.sub(r'\*(.+?)\*', r'\1', response_text, flags=re.DOTALL)
        response_text = re.sub(r'_(.+?)_', r'\1', response_text)
        response_text = re.sub(r'`(.+?)`', r'\1', response_text)
        response_text = re.sub(r'^#{1,6}\s+', '', response_text, flags=re.MULTILINE)

        # 4. 이모지 제거 — NSFW 장면(arousal 41+): 전면 금지 / SFW: 2개 이상이면 제거
        emoji_pat = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FAFF"
            "]+", flags=re.UNICODE
        )
        emoji_count = len(emoji_pat.findall(response_text))
        nsfw_active = scene_ctx.get('in_scene', False) or new_arousal >= 41 or is_afterglow
        if nsfw_active and emoji_count >= 1:
            response_text = emoji_pat.sub('', response_text)
            logger.debug(f"Emoji removed (NSFW, count={emoji_count})")
        elif not nsfw_active and emoji_count >= 2:
            response_text = emoji_pat.sub('', response_text)
            logger.debug(f"Emoji overflow ({emoji_count}) cleaned")

        # 5. ~요 경어체 → 반말 변환
        response_text = fix_polite_endings(response_text)

        # 6. NSFW 질문 패턴 제거
        response_text = remove_nsfw_questions(response_text, scene_ctx.get('in_scene', False))

        # 7. 응원단/코치 멘트 제거
        response_text = remove_coach_phrases(response_text)

        # 8. 단독 마침표 제거 (... 은 보존)
        response_text = re.sub(r'(?<!\.)\.(?!\.)', ' ', response_text)

        # 9. 연속 공백 정리
        response_text = re.sub(r' {2,}', ' ', response_text).strip()

        # 10. 미러링 감지 (유저 텍스트로 시작하면 제거)
        user_stripped = user_text.strip()
        if len(user_stripped) >= 2 and response_text.startswith(user_stripped):
            response_text = response_text[len(user_stripped):].strip()
            if not response_text:
                response_text = "으음... 나도"
            logger.warning(f"Mirroring trimmed for {user_id}")

        # 11. 빈 응답 방어
        if not response_text.strip():
            logger.warning("Empty response from Ollama")
            response_text = "으음..."

        db.save_message(user_id, "assistant", response_text)

        # 자동 요약
        if db.get_conversation_count(user_id) >= 50:
            asyncio.create_task(auto_summarize(user_id, character_name))

        # 전송
        if len(response_text) > 4096:
            for i in range(0, len(response_text), 4096):
                await update.message.reply_text(response_text[i:i+4096])
        else:
            await update.message.reply_text(response_text)

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        await update.message.reply_text(f"응답 생성 중 오류: {str(e)}")


# ──────────────────────────────────────────────
# 봇 커맨드 등록
# ──────────────────────────────────────────────

async def set_commands(application: Application):
    commands = [
        BotCommand("start",     "봇 시작하기"),
        BotCommand("reset",     "대화 초기화"),
        BotCommand("character", "캐릭터 정보"),
        BotCommand("switch",    "캐릭터 변경"),
        BotCommand("help",      "도움말"),
    ]
    await application.bot.set_my_commands(commands)


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────

def main():
    global db, ollama_client, config

    config = load_config()
    if config.get('telegram_token') == 'YOUR_BOT_TOKEN_HERE':
        print("ERROR: Please set your Telegram bot token in config.json")
        sys.exit(1)

    db = Database("gf_bot.db")
    logger.info("Database initialized")

    ollama_client = OllamaClient(
        base_url=config.get('ollama_url', 'http://localhost:11434'),
        model=config.get('model', 'huihui_ai/exaone3.5-abliterated:7.8b'),
        keep_alive=config.get('keep_alive', '30m')
    )
    logger.info(f"Ollama client initialized: {config.get('model')}")

    init_characters()
    if not characters:
        print("WARNING: No characters loaded. Check characters/ directory")

    application = Application.builder().token(config.get('telegram_token')).build()
    application.add_handler(CommandHandler("start",     start))
    application.add_handler(CommandHandler("reset",     reset))
    application.add_handler(CommandHandler("character", character))
    application.add_handler(CommandHandler("switch",    switch_character))
    application.add_handler(CommandHandler("help",      help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.post_init = set_commands

    KST = timezone(timedelta(hours=9))
    jq = application.job_queue
    jq.run_daily(send_morning_greeting,    time=dtime(8,  0, 0, tzinfo=KST), name="morning")
    jq.run_daily(send_night_greeting,      time=dtime(23, 0, 0, tzinfo=KST), name="night")
    jq.run_daily(update_all_days_together, time=dtime(0,  0, 0, tzinfo=KST), name="days")
    logger.info("Schedulers registered")

    logger.info("Starting bot...")
    print("Bot started. Press Ctrl+C to stop.")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("Bot stopped.")


if __name__ == '__main__':
    main()
