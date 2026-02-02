#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立测试播放历史记录数据库功能（不依赖 xbmc 模块）
"""

import sqlite3
import time
import os
import sys

# 设置输出编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class MockXbmc:
    """模拟 xbmc 模块"""
    class LOGDEBUG:
        pass

    class LOGERROR:
        pass

    class LOGINFO:
        pass

    @staticmethod
    def log(msg, level=None):
        print(f"[LOG] {msg}")


# 模拟 xbmc 模块
sys.modules['xbmc'] = MockXbmc
sys.modules['xbmcaddon'] = MockXbmc


# 定义常量
CACHE_DB_PATH = os.path.join(os.path.dirname(__file__), 'test_cache.db')
ADDON_ID = 'plugin.audio.music'


def get_cache_db():
    """获取缓存数据库实例"""
    class CacheDB:
        def __init__(self):
            self.conn = None
            self.cursor = None
            self._connect()

        def _connect(self):
            """连接数据库"""
            try:
                self.conn = sqlite3.connect(CACHE_DB_PATH, check_same_thread=False)
                self.cursor = self.conn.cursor()
                self._create_tables()
            except Exception as e:
                print(f'[Error] CacheDB connect error: {e}')

        def _create_tables(self):
            """创建缓存表"""
            # 专辑封面缓存表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS album_covers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    album_id INTEGER UNIQUE NOT NULL,
                    cover_url TEXT NOT NULL,
                    timestamp INTEGER NOT NULL
                )
            ''')

            # 播放历史记录表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS play_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    song_id INTEGER NOT NULL,
                    song_name TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    artist_id INTEGER NOT NULL,
                    album TEXT NOT NULL,
                    album_id INTEGER NOT NULL,
                    pic TEXT,
                    duration INTEGER NOT NULL,
                    play_time INTEGER NOT NULL,
                    UNIQUE(song_id)
                )
            ''')

            # 为 play_time 创建索引，方便按时间查询
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_play_history_play_time
                ON play_history(play_time DESC)
            ''')

            self.conn.commit()

        def add_play_history(self, song_id, song_name, artist, artist_id, album, album_id, pic, duration):
            """添加播放历史记录"""
            try:
                play_time = int(time.time())
                self.cursor.execute('''
                    INSERT OR REPLACE INTO play_history
                    (song_id, song_name, artist, artist_id, album, album_id, pic, duration, play_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (song_id, song_name, artist, artist_id, album, album_id, pic, duration, play_time))
                self.conn.commit()
                print(f'[Debug] Play history added: {artist} - {song_name}')
                return True
            except Exception as e:
                print(f'[Error] Error adding play history: {e}')
                return False

        def get_play_history(self, limit=None, days=None):
            """获取播放历史记录"""
            try:
                query = 'SELECT song_id, song_name, artist, artist_id, album, album_id, pic, duration, play_time FROM play_history'
                params = []

                if days is not None:
                    current_time = int(time.time())
                    cutoff_time = current_time - (days * 24 * 60 * 60)
                    query += ' WHERE play_time >= ?'
                    params.append(cutoff_time)

                query += ' ORDER BY play_time DESC'

                if limit is not None:
                    query += ' LIMIT ?'
                    params.append(limit)

                self.cursor.execute(query, params)
                rows = self.cursor.fetchall()

                history = []
                for row in rows:
                    history.append({
                        'id': row[0],
                        'name': row[1],
                        'artist': row[2],
                        'artist_id': row[3],
                        'album': row[4],
                        'album_id': row[5],
                        'pic': row[6],
                        'dt': row[7],
                        'time': row[8]
                    })

                print(f'[Debug] Retrieved {len(history)} play history records')
                return history

            except Exception as e:
                print(f'[Error] Error getting play history: {e}')
                return []

        def clear_play_history(self):
            """清空播放历史记录"""
            try:
                self.cursor.execute('DELETE FROM play_history')
                self.conn.commit()
                print('[Info] Play history cleared')
                return True
            except Exception as e:
                print(f'[Error] Error clearing play history: {e}')
                return False

        def get_play_history_by_artist(self, artist):
            """获取指定艺术家的播放历史"""
            try:
                self.cursor.execute('''
                    SELECT song_id, song_name, artist, artist_id, album, album_id, pic, duration, play_time
                    FROM play_history
                    WHERE artist = ?
                    ORDER BY play_time DESC
                ''', (artist,))
                rows = self.cursor.fetchall()

                history = []
                for row in rows:
                    history.append({
                        'id': row[0],
                        'name': row[1],
                        'artist': row[2],
                        'artist_id': row[3],
                        'album': row[4],
                        'album_id': row[5],
                        'pic': row[6],
                        'dt': row[7],
                        'time': row[8]
                    })

                print(f'[Debug] Retrieved {len(history)} play history records for artist: {artist}')
                return history

            except Exception as e:
                print(f'[Error] Error getting play history by artist: {e}')
                return []

        def get_play_history_by_album(self, album):
            """获取指定专辑的播放历史"""
            try:
                self.cursor.execute('''
                    SELECT song_id, song_name, artist, artist_id, album, album_id, pic, duration, play_time
                    FROM play_history
                    WHERE album = ?
                    ORDER BY play_time DESC
                ''', (album,))
                rows = self.cursor.fetchall()

                history = []
                for row in rows:
                    history.append({
                        'id': row[0],
                        'name': row[1],
                        'artist': row[2],
                        'artist_id': row[3],
                        'album': row[4],
                        'album_id': row[5],
                        'pic': row[6],
                        'dt': row[7],
                        'time': row[8]
                    })

                print(f'[Debug] Retrieved {len(history)} play history records for album: {album}')
                return history

            except Exception as e:
                print(f'[Error] Error getting play history by album: {e}')
                return []

    return CacheDB()


def test_history_db():
    """测试历史记录数据库功能"""
    print("=" * 60)
    print("测试播放历史记录数据库功能")
    print("=" * 60)

    cache_db = get_cache_db()

    # 1. 清空历史记录
    print("\n1. 清空历史记录...")
    cache_db.clear_play_history()
    history = cache_db.get_play_history()
    print(f"   历史记录数量: {len(history)}")
    assert len(history) == 0, "清空失败"
    print("   ✓ 清空成功")

    # 2. 添加测试数据
    print("\n2. 添加测试数据...")
    test_songs = [
        {
            "song_id": 1,
            "song_name": "测试歌曲1",
            "artist": "测试歌手A",
            "artist_id": 101,
            "album": "测试专辑X",
            "album_id": 201,
            "pic": "https://example.com/pic1.jpg",
            "duration": 180
        },
        {
            "song_id": 2,
            "song_name": "测试歌曲2",
            "artist": "测试歌手A",
            "artist_id": 101,
            "album": "测试专辑X",
            "album_id": 201,
            "pic": "https://example.com/pic2.jpg",
            "duration": 200
        },
        {
            "song_id": 3,
            "song_name": "测试歌曲3",
            "artist": "测试歌手B",
            "artist_id": 102,
            "album": "测试专辑Y",
            "album_id": 202,
            "pic": "https://example.com/pic3.jpg",
            "duration": 220
        },
    ]

    for song in test_songs:
        cache_db.add_play_history(**song)
        print(f"   添加: {song['song_name']} - {song['artist']}")

    # 3. 获取所有历史记录
    print("\n3. 获取所有历史记录...")
    history = cache_db.get_play_history()
    print(f"   历史记录数量: {len(history)}")
    for h in history:
        print(f"   - {h['name']} - {h['artist']} (ID: {h['id']})")
    assert len(history) == 3, "获取历史记录失败"
    print("   ✓ 获取成功")

    # 4. 测试按艺术家查询
    print("\n4. 测试按艺术家查询...")
    artist_history = cache_db.get_play_history_by_artist("测试歌手A")
    print(f"   测试歌手A 的歌曲数量: {len(artist_history)}")
    for h in artist_history:
        print(f"   - {h['name']}")
    assert len(artist_history) == 2, "按艺术家查询失败"
    print("   ✓ 按艺术家查询成功")

    # 5. 测试按专辑查询
    print("\n5. 测试按专辑查询...")
    album_history = cache_db.get_play_history_by_album("测试专辑X")
    print(f"   测试专辑X 的歌曲数量: {len(album_history)}")
    for h in album_history:
        print(f"   - {h['name']}")
    assert len(album_history) == 2, "按专辑查询失败"
    print("   ✓ 按专辑查询成功")

    # 6. 测试按天数过滤
    print("\n6. 测试按天数过滤...")
    recent_history = cache_db.get_play_history(days=7)
    print(f"   最近7天的歌曲数量: {len(recent_history)}")
    assert len(recent_history) == 3, "按天数过滤失败"
    print("   ✓ 按天数过滤成功")

    # 7. 测试限制数量
    print("\n7. 测试限制数量...")
    limited_history = cache_db.get_play_history(limit=2)
    print(f"   限制2首的歌曲数量: {len(limited_history)}")
    assert len(limited_history) == 2, "限制数量失败"
    print("   ✓ 限制数量成功")

    # 8. 测试去重（重复添加同一首歌）
    print("\n8. 测试去重...")
    cache_db.add_play_history(
        song_id=1,
        song_name="测试歌曲1",
        artist="测试歌手A",
        artist_id=101,
        album="测试专辑X",
        album_id=201,
        pic="https://example.com/pic1.jpg",
        duration=180
    )
    history = cache_db.get_play_history()
    print(f"   重复添加后的历史记录数量: {len(history)}")
    assert len(history) == 3, "去重失败"
    print("   ✓ 去重成功")

    # 9. 清空测试数据
    print("\n9. 清空测试数据...")
    cache_db.clear_play_history()
    history = cache_db.get_play_history()
    print(f"   清空后的历史记录数量: {len(history)}")
    assert len(history) == 0, "清空失败"
    print("   ✓ 清空成功")

    # 清理测试数据库文件
    if os.path.exists(CACHE_DB_PATH):
        os.remove(CACHE_DB_PATH)
        print(f"\n已清理测试数据库文件: {CACHE_DB_PATH}")

    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    test_history_db()
