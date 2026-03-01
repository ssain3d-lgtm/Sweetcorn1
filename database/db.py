import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any


class Database:
    def __init__(self, db_path: str = "gf_bot.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                nickname TEXT,
                character TEXT DEFAULT 'hana',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # User profiles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                mood TEXT DEFAULT 'normal',
                days_together INTEGER DEFAULT 0,
                summary TEXT,
                preferences TEXT,
                arousal INTEGER DEFAULT 0,
                affection INTEGER DEFAULT 30,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # 기존 DB에 컬럼이 없을 경우 마이그레이션
        try:
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN arousal INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN affection INTEGER DEFAULT 30")
        except Exception:
            pass

        conn.commit()
        conn.close()

    def get_or_create_user(self, user_id: int, username: str = None, nickname: str = None, character: str = "hana") -> Dict[str, Any]:
        """Get or create user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

        if user:
            conn.close()
            return {
                'user_id': user[0],
                'username': user[1],
                'nickname': user[2],
                'character': user[3],
                'created_at': user[4],
                'last_seen': user[5]
            }
        
        # Create new user
        cursor.execute("""
            INSERT INTO users (user_id, username, nickname, character)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, nickname or username, character))

        # Create user profile
        cursor.execute("""
            INSERT INTO user_profiles (user_id, mood, days_together)
            VALUES (?, 'normal', 0)
        """, (user_id,))

        conn.commit()
        conn.close()

        return {
            'user_id': user_id,
            'username': username,
            'nickname': nickname or username,
            'character': character,
            'created_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat()
        }

    def save_message(self, user_id: int, role: str, content: str):
        """Save message to conversation history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO conversations (user_id, role, content)
            VALUES (?, ?, ?)
        """, (user_id, role, content))

        conn.commit()
        conn.close()

    def get_recent_messages(self, user_id: int, limit: int = 50) -> List[Dict[str, str]]:
        """Get recent messages for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT role, content, timestamp
            FROM conversations
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))

        messages = cursor.fetchall()
        conn.close()

        # Reverse to get chronological order
        return [
            {
                'role': msg[0],
                'content': msg[1],
                'timestamp': msg[2]
            }
            for msg in reversed(messages)
        ]

    def update_mood(self, user_id: int, mood: str):
        """Update user mood"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE user_profiles
            SET mood = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (mood, user_id))

        conn.commit()
        conn.close()

    def update_summary(self, user_id: int, summary: str):
        """Update user conversation summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE user_profiles
            SET summary = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (summary, user_id))

        conn.commit()
        conn.close()

    def get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Get user profile"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        profile = cursor.fetchone()
        conn.close()

        if not profile:
            return {}

        preferences = {}
        if profile[4]:
            try:
                preferences = json.loads(profile[4])
            except json.JSONDecodeError:
                preferences = {}

        return {
            'user_id': profile[0],
            'mood': profile[1],
            'days_together': profile[2],
            'summary': profile[3],
            'preferences': preferences,
            'updated_at': profile[5]
        }

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user info"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()

        if not user:
            return None

        return {
            'user_id': user[0],
            'username': user[1],
            'nickname': user[2],
            'character': user[3],
            'created_at': user[4],
            'last_seen': user[5]
        }

    def reset_conversation(self, user_id: int):
        """Reset user conversation history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        cursor.execute("""
            UPDATE user_profiles
            SET summary = NULL, mood = 'normal', days_together = 0
            WHERE user_id = ?
        """, (user_id,))

        conn.commit()
        conn.close()

    def set_character(self, user_id: int, character: str):
        """Set user character"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users
            SET character = ?
            WHERE user_id = ?
        """, (character, user_id))

        conn.commit()
        conn.close()

    def update_character(self, user_id: int, character: str):
        """Alias for set_character (used by /switch command)"""
        self.set_character(user_id, character)

    def update_last_seen(self, user_id: int):
        """Update last seen timestamp"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users
            SET last_seen = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))

        conn.commit()
        conn.close()

    # ──────────────────────────────────────────────
    # 2주차 추가 메서드
    # ──────────────────────────────────────────────

    def get_all_users(self) -> List[Dict[str, Any]]:
        """모든 유저 목록 반환 (스케줄러 인사 메시지용)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, character, last_seen FROM users")
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'user_id': row[0],
                'username': row[1],
                'character': row[2],
                'last_seen': row[3],
            }
            for row in rows
        ]

    def get_conversation_count(self, user_id: int) -> int:
        """유저의 현재 대화 턴 수 반환 (자동 요약 트리거 판단용)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM conversations WHERE user_id = ?",
            (user_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def update_preferences(self, user_id: int, new_prefs: Dict[str, str]):
        """
        취향 정보를 기존 데이터와 병합해서 저장.
        new_prefs: {'food': '중식', 'activity': '게임'} 형태
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 기존 preferences 읽기
        cursor.execute(
            "SELECT preferences FROM user_profiles WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        existing: Dict[str, str] = {}
        if row and row[0]:
            try:
                existing = json.loads(row[0])
            except json.JSONDecodeError:
                existing = {}

        # 병합 (새 값으로 덮어씀)
        existing.update(new_prefs)

        cursor.execute("""
            UPDATE user_profiles
            SET preferences = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (json.dumps(existing, ensure_ascii=False), user_id))

        conn.commit()
        conn.close()

    def archive_old_messages(self, user_id: int, keep_count: int = 10):
        """
        오래된 대화를 삭제하고 최신 keep_count개만 유지.
        자동 요약 후 호출해서 메모리/DB 용량 절약.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 최신 keep_count개의 id 구하기
        cursor.execute("""
            SELECT id FROM conversations
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, keep_count))
        keep_ids = [row[0] for row in cursor.fetchall()]

        if keep_ids:
            placeholders = ','.join('?' * len(keep_ids))
            cursor.execute(
                f"DELETE FROM conversations WHERE user_id = ? AND id NOT IN ({placeholders})",
                [user_id] + keep_ids
            )

        conn.commit()
        conn.close()

    def get_arousal_affection(self, user_id: int) -> Dict[str, int]:
        """현재 arousal, affection 수치 반환"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT arousal, affection FROM user_profiles WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {'arousal': 0, 'affection': 30}
        return {'arousal': row[0] or 0, 'affection': row[1] or 30}

    def update_arousal(self, user_id: int, new_arousal: int):
        """arousal 수치 업데이트 (0~100 클램프)"""
        new_arousal = max(0, min(100, new_arousal))
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profiles
            SET arousal = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (new_arousal, user_id))
        conn.commit()
        conn.close()

    def update_affection(self, user_id: int, new_affection: int):
        """affection 수치 업데이트 (0~100 클램프)"""
        new_affection = max(0, min(100, new_affection))
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profiles
            SET affection = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (new_affection, user_id))
        conn.commit()
        conn.close()

    def increment_days_together(self, user_id: int):
        """days_together 1 증가 (매일 자정 스케줄러 호출)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profiles
            SET days_together = days_together + 1, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))
        conn.commit()
        conn.close()
