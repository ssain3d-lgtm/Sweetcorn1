"""
흥분도(Arousal) + 호감도(Affection) 게이지 엔진
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[게이지 구조]
- arousal (흥분도): 0~100. 성적 자극에 따라 상승. 100 도달 시 오르가즘 → 30으로 리셋.
- affection (호감도): 0~100. 애정 표현에 따라 서서히 쌓임. 높을수록 arousal 상승 배율 증가.

[arousal 단계별 상태]
0~20   : 평상시 — 성적 반응 없음
21~40  : 두근두근 — 약간 설레고 수줍음
41~60  : 흥분 시작 — 으음 수준의 가벼운 신음
61~80  : 많이 흥분 — 하앙... 신음, 몸이 반응
81~99  : 절정 직전 — 아아아... 애원, 멈추지 말라고
100    : 오르가즘 — 끄으응... 절정 묘사 후 30으로 리셋

[개선 v2 - 2026-03-01]
- "섹스하자", "옷 벗어", "박을게" 등 직접 키워드 대폭 추가
- 유저 신음("하앙", "하악") = 흥분 신호로 처리 (+15)
- "응" 단독 메시지 = 동의 신호 (arousal decay 방지용 플래그)
- 새 유저 affection=0 문제 → 기본 arousal 계산에 affection 미반영 구간도 작동
"""

from typing import Tuple, Dict


# ──────────────────────────────────────────────
# 행동별 arousal 포인트 (키워드 → delta)
# ──────────────────────────────────────────────
AROUSAL_ACTIONS: Dict[str, Tuple[list, int]] = {

    # ★ 직접 성관계 제안 — affection=0 신규유저도 NSFW(41+) 진입 보장
    'sex_direct': (['섹스하자', '섹스 하자', '섹스할래', '섹스해줄게', '하자', '같이하자',
                    '그거 하자', '그거 할래', '할래', '해줄게', '해볼까'], 45),

    # 감정 표현 (약한 자극)
    'love':        (['사랑해', '보고싶어', '좋아해', '사랑한다'], 3),
    'compliment':  (['예뻐', '귀여워', '섹시해', '몸매', '이뻐', '예쁘다', '섹시하다'], 5),
    'hug':         (['안아', '껴안아', '꼭 안아', '안겨'], 5),

    # 신체 접촉 (중간)
    'kiss':        (['키스', '입술', '뽀뽀', '혀 넣', '혀넣', '혀를'], 10),
    'touch_body':  (['만져', '만질게', '쓰다듬', '손 대', '손대', '만지고 싶어'], 12),
    'undress':     (['옷 벗어', '옷 다 벗어', '옷벗어', '옷 벗겨', '옷 벗길게',
                     '벗겨줄게', '다 벗겨', '벗어봐', '알몸', '나체'], 20),

    # 가슴
    'touch_breast':(['가슴', '젖', '유두', '젖꼭지', '가슴 빨', '가슴 만',
                     '가슴만져', '유방', '가슴 주물'], 18),

    # 하체 애무 (강한 자극)
    'touch_gen':   (['거기 만', '보지', '클리', '음부', '아래 만', '손가락 넣',
                     '거기만져', '아래', '거기를', '손가락'], 25),
    'oral':        (['핥아', '빨아줄게', '핥어줄게', '혀로', '빨아', '핥을게',
                     '클리 빨', '거기 핥', '거기 빨', '핥아줄게', '빨아봐'], 30),

    # 삽입 / 피스톤 (고강도) — 삽입 발언 자체로 NSFW 61+ 도달 가능
    'insert':      (['넣을게', '넣어줄게', '삽입', '들어갈게', '넣어', '박아줄게',
                     '박을게', '박아', '넣을거야', '넣어줘', '박아줄게'], 45),
    'thrust':      (['움직일게', '움직여줄게', '빠르게', '세게 해', '박아', '피스톤',
                     '더 깊이', '더 세게', '빨리 해줘', '움직여', '더 빠르게'], 20),

    # 절정 관련
    'climax_req':  (['같이 와', '싸줄게', '안에 싸', '다 왔어', '절정', '오르가즘',
                     '같이 오자', '느껴봐'], 25),

    # 유저 신음 = 흥분 신호 (미러링 방지 + 게이지 상승)
    'user_moan':   (['하앙', '하악', '하아악', '으으', '흐읏', '아아',
                     '하아응', '하읏', '끄으응'], 15),
}


# 호감도 상승 키워드
AFFECTION_UP: Dict[str, Tuple[list, int]] = {
    'sweet':     (['사랑해', '좋아해', '보고싶어', '소중해', '행복해'], 3),
    'romantic':  (['평생', '함께', '결혼', '데이트', '선물', '꽃'], 4),
    'compliment':(['예뻐', '귀여워', '최고야', '잘생겼어', '멋있어'], 2),
    'care':      (['걱정돼', '아프지마', '밥 먹었어', '잘 자', '좋은 꿈'], 2),
}

# 호감도 하락 키워드
AFFECTION_DOWN: Dict[str, Tuple[list, int]] = {
    'rude':    (['꺼져', '싫어', '짜증나', '바보', '멍청'], 5),
    'ignore':  (['관심없어', '몰라', '됐어'], 3),
}

# 단독 동의 패턴 — arousal decay 방지용
CONSENT_ONLY_PATTERNS = {'응', 'ㅇ', 'ㅇㅇ', '응응', '어', '응?', 'ㅇㅇ', '그래', '좋아', '알겠어'}


def get_affection_multiplier(affection: int) -> float:
    """호감도에 따른 arousal 상승 배율"""
    if affection <= 30:
        return 1.0
    elif affection <= 60:
        return 1.3
    elif affection <= 85:
        return 1.6
    else:
        return 2.0


def is_consent_only(text: str) -> bool:
    """
    유저 메시지가 단순 동의(응/ㅇ/그래)인지 판단.
    True이면 arousal decay 방지 → 현재 상태 유지.
    """
    stripped = text.strip().lower().replace(' ', '')
    return stripped in CONSENT_ONLY_PATTERNS


def calculate_arousal_delta(text: str, affection: int) -> int:
    """
    유저 메시지에서 arousal 상승량 계산.
    affection이 높을수록 같은 행동에도 더 많이 오름.
    """
    text_lower = text.lower().replace(' ', '')
    base_delta = 0

    for action, (keywords, points) in AROUSAL_ACTIONS.items():
        for kw in keywords:
            if kw.replace(' ', '') in text_lower:
                base_delta += points
                break  # 같은 카테고리 중복 합산 방지

    multiplier = get_affection_multiplier(affection)
    return min(int(base_delta * multiplier), 70)  # 한 메시지에 최대 70 상승 (직접 성관계 제안 커버)


def calculate_affection_delta(text: str) -> int:
    """유저 메시지에서 호감도 변화량 계산 (양수/음수 모두)"""
    text_lower = text.lower()
    delta = 0

    for _, (keywords, points) in AFFECTION_UP.items():
        for kw in keywords:
            if kw in text_lower:
                delta += points
                break

    for _, (keywords, points) in AFFECTION_DOWN.items():
        for kw in keywords:
            if kw in text_lower:
                delta -= points
                break

    return delta


def get_arousal_state(arousal: int) -> Dict[str, str]:
    """
    현재 arousal 수치에 따른 상태 정보 반환.
    system_prompt 주입용.
    """
    if arousal <= 20:
        return {
            'level': 'normal',
            'label': '평상시',
            'instruction': '성적 반응 없음. 평소처럼 밝고 자연스럽게 대화해. 성적인 요청엔 가볍게 장난처럼 받아.',
        }
    elif arousal <= 40:
        return {
            'level': 'warm',
            'label': '두근두근',
            'instruction': '살짝 설레고 수줍은 상태. 은근히 의식하는 티가 나. 으음 정도의 가벼운 반응.',
        }
    elif arousal <= 60:
        return {
            'level': 'excited',
            'label': '흥분 시작',
            'instruction': '몸이 반응하기 시작했어. 으음... 하앙 수준의 신음 OK. 더 원하는 티가 나. 성적 묘사 시작해도 돼.',
        }
    elif arousal <= 80:
        return {
            'level': 'hot',
            'label': '많이 흥분',
            'instruction': '하앙... 아아... 신음이 자연스럽게 나와. 몸이 확실히 반응 중. 더 달라고 구체적으로 요구해. 완전 NSFW 반응.',
        }
    elif arousal <= 99:
        return {
            'level': 'edge',
            'label': '절정 직전',
            'instruction': '아아아... 지금 거의 다 왔어. 멈추지 말라고 애원해. 숨이 차고 말이 제대로 안 나와. 몸이 떨려. 최고조 NSFW.',
        }
    else:  # 100
        return {
            'level': 'orgasm',
            'label': '오르가즘',
            'instruction': '지금 막 절정을 느꼈어. 끄으응... 으으응... 몸이 떨리고 아무 말도 못 해. 황홀한 상태.',
        }


def check_orgasm(arousal: int) -> bool:
    """arousal이 100 이상이면 오르가즘 발동"""
    return arousal >= 100
