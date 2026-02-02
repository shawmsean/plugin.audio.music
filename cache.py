# -*- coding:utf-8 -*-
"""
SQLite 缓存模块
用于缓存专辑封面、歌单等数据，提高读取速度
"""

import os
import time
import json
import sqlite3
import hashlib
import xbmc
import xbmcvfs
import xbmcaddon
import threading

try:
    xbmc.translatePath = xbmcvfs.translatePath
except AttributeError:
    pass

__addon__ = xbmcaddon.Addon()
__addon_id__ = __addon__.getAddonInfo('id')
PROFILE = xbmc.translatePath(__addon__.getAddonInfo('profile'))
CACHE_DB_PATH = os.path.join(PROFILE, 'cache.db')

# 线程本地存储，每个线程独立的数据库连接
_thread_local = threading.local()


def get_cache_db():
    """
    获取当前线程的缓存数据库实例
    每个线程有独立的数据库连接，避免并发问题

    Returns:
        CacheDB: 缓存数据库实例
    """
    # 检查当前线程是否已有连接
    if not hasattr(_thread_local, 'cache_db') or _thread_local.cache_db is None:
        _thread_local.cache_db = CacheDB()
    return _thread_local.cache_db


class CacheDB:
    """SQLite 缓存数据库管理类"""

    def __init__(self):
        self.conn = None
        self.cursor = None
        self._connect()

    def _connect(self):
        """连接数据库"""
        try:
            # check_same_thread=False 允许跨线程使用连接（但每个线程应该有自己的连接）
            self.conn = sqlite3.connect(CACHE_DB_PATH, check_same_thread=False)
            self.cursor = self.conn.cursor()
            self._create_tables()
        except Exception as e:
            xbmc.log('[%s] CacheDB connect error: %s' % (__addon_id__, str(e)), xbmc.LOGERROR)

    def _create_tables(self):
        """创建缓存表"""
        # 缓存表: id, key, data, timestamp, expire_seconds, type
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                data TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                expire_seconds INTEGER NOT NULL,
                type TEXT NOT NULL
            )
        ''')

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

    def get_cache_expire_seconds(self):
        """
        从设置中获取缓存过期时间（秒）

        Returns:
            int: 缓存过期时间（秒）
        """
        # 获取设置中的缓存过期时间选项
        cache_expire_option = __addon__.getSetting('cache_expire_time')

        # 根据选项返回对应的秒数
        # 选项值: "0"=1小时, "1"=6小时, "2"=12小时, "3"=24小时, "4"=3天, "5"=7天
        expire_time_map = {
            '0': 1 * 60 * 60,      # 1 小时
            '1': 6 * 60 * 60,      # 6 小时
            '2': 12 * 60 * 60,     # 12 小时
            '3': 24 * 60 * 60,     # 24 小时
            '4': 3 * 24 * 60 * 60, # 3 天
            '5': 7 * 24 * 60 * 60  # 7 天
        }

        # 默认返回 24 小时
        return expire_time_map.get(cache_expire_option, 24 * 60 * 60)

    def is_cache_enabled(self):
        """
        检查缓存是否启用

        Returns:
            bool: 是否启用缓存
        """
        return __addon__.getSetting('cache_enabled') == 'true'

    def get_auto_clear_cache(self):
        """
        检查是否自动清理过期缓存

        Returns:
            bool: 是否自动清理过期缓存
        """
        return __addon__.getSetting('auto_clear_cache') == 'true'

    def generate_cache_key(self, prefix, *args):
        """
        生成缓存键

        Args:
            prefix: 缓存前缀 (如 'album_cover', 'playlist', 'playlist_detail')
            *args: 缓存参数 (如分类、偏移量、ID等)

        Returns:
            str: MD5 缓存键
        """
        cache_string = '%s_%s' % (prefix, '_'.join(str(arg) for arg in args))
        return hashlib.md5(cache_string.encode()).hexdigest()

    def get(self, key):
        """
        从缓存读取数据

        Args:
            key: 缓存键

        Returns:
            dict: 缓存数据, 或 None 如果缓存不存在或已过期
        """
        if not self.is_cache_enabled():
            return None

        try:
            # 查询缓存
            self.cursor.execute('''
                SELECT data, timestamp, expire_seconds
                FROM cache
                WHERE key = ?
            ''', (key,))
            result = self.cursor.fetchone()

            if result is None:
                xbmc.log('[%s] Cache miss: %s' % (__addon_id__, key), xbmc.LOGDEBUG)
                return None

            data, timestamp, expire_seconds = result
            current_time = int(time.time())

            # 检查是否过期
            if (current_time - timestamp) > expire_seconds:
                xbmc.log('[%s] Cache expired: %s (age: %d seconds)' %
                         (__addon_id__, key, current_time - timestamp), xbmc.LOGDEBUG)
                # 删除过期缓存
                self.delete(key)
                return None

            xbmc.log('[%s] Cache hit: %s (age: %d seconds)' %
                     (__addon_id__, key, current_time - timestamp), xbmc.LOGDEBUG)
            return json.loads(data)

        except Exception as e:
            xbmc.log('[%s] Error reading cache: %s - %s' % (__addon_id__, key, str(e)), xbmc.LOGERROR)
            return None

    def set(self, key, data, cache_type='default', expire_seconds=None):
        """
        写入缓存数据

        Args:
            key: 缓存键
            data: 要缓存的数据 (必须是 JSON 可序列化的)
            cache_type: 缓存类型 (album_cover, playlist, etc.)
            expire_seconds: 过期时间（秒），None 则使用设置中的默认值

        Returns:
            bool: True 表示成功, False 表示失败
        """
        if not self.is_cache_enabled():
            return False

        try:
            if expire_seconds is None:
                expire_seconds = self.get_cache_expire_seconds()

            timestamp = int(time.time())
            json_data = json.dumps(data, ensure_ascii=False)

            # 插入或更新缓存
            self.cursor.execute('''
                INSERT OR REPLACE INTO cache (key, data, timestamp, expire_seconds, type)
                VALUES (?, ?, ?, ?, ?)
            ''', (key, json_data, timestamp, expire_seconds, cache_type))
            self.conn.commit()

            xbmc.log('[%s] Cache written: %s (type: %s, expire: %d seconds)' %
                     (__addon_id__, key, cache_type, expire_seconds), xbmc.LOGDEBUG)
            return True

        except Exception as e:
            xbmc.log('[%s] Error writing cache: %s - %s' % (__addon_id__, key, str(e)), xbmc.LOGERROR)
            return False

    def delete(self, key):
        """
        删除指定缓存

        Args:
            key: 缓存键

        Returns:
            bool: True 表示成功, False 表示失败
        """
        try:
            self.cursor.execute('DELETE FROM cache WHERE key = ?', (key,))
            self.conn.commit()
            xbmc.log('[%s] Cache deleted: %s' % (__addon_id__, key), xbmc.LOGDEBUG)
            return True
        except Exception as e:
            xbmc.log('[%s] Error deleting cache: %s - %s' % (__addon_id__, key, str(e)), xbmc.LOGERROR)
            return False

    def delete_by_type(self, cache_type):
        """
        删除指定类型的所有缓存

        Args:
            cache_type: 缓存类型

        Returns:
            int: 删除的缓存数量
        """
        try:
            self.cursor.execute('DELETE FROM cache WHERE type = ?', (cache_type,))
            deleted_count = self.cursor.rowcount
            self.conn.commit()
            xbmc.log('[%s] Deleted %d caches of type: %s' % (__addon_id__, deleted_count, cache_type), xbmc.LOGINFO)
            return deleted_count
        except Exception as e:
            xbmc.log('[%s] Error deleting caches by type: %s - %s' % (__addon_id__, cache_type, str(e)), xbmc.LOGERROR)
            return 0

    def clear_expired(self):
        """
        清理所有过期缓存

        Returns:
            int: 删除的缓存数量
        """
        if not self.get_auto_clear_cache():
            return 0

        try:
            current_time = int(time.time())
            self.cursor.execute('''
                DELETE FROM cache
                WHERE (timestamp + expire_seconds) < ?
            ''', (current_time,))
            deleted_count = self.cursor.rowcount
            self.conn.commit()
            xbmc.log('[%s] Cleared %d expired caches' % (__addon_id__, deleted_count), xbmc.LOGINFO)

            # 清理过期的专辑封面缓存
            album_cover_deleted = self.clear_expired_album_covers()

            return deleted_count + album_cover_deleted
        except Exception as e:
            xbmc.log('[%s] Error clearing expired caches: %s' % (__addon_id__, str(e)), xbmc.LOGERROR)
            return 0

    def clear_all(self):
        """
        清理所有缓存

        Returns:
            int: 删除的缓存数量
        """
        try:
            self.cursor.execute('DELETE FROM cache')
            self.cursor.execute('DELETE FROM album_covers')  # 清理专辑封面缓存
            deleted_count = self.cursor.rowcount
            self.conn.commit()
            xbmc.log('[%s] Cleared all caches: %d items' % (__addon_id__, deleted_count), xbmc.LOGINFO)
            return deleted_count
        except Exception as e:
            xbmc.log('[%s] Error clearing all caches: %s' % (__addon_id__, str(e)), xbmc.LOGERROR)
            return 0

    # ========== 专辑封面缓存方法 ==========

    def get_album_cover(self, album_id):
        """
        获取专辑封面 URL

        Args:
            album_id: 专辑 ID

        Returns:
            str: 封面 URL，或 None 如果未缓存
        """
        if not self.is_cache_enabled():
            return None

        try:
            self.cursor.execute('''
                SELECT cover_url, timestamp
                FROM album_covers
                WHERE album_id = ?
            ''', (album_id,))
            result = self.cursor.fetchone()

            if result is None:
                xbmc.log('[%s] Album cover cache miss: %s' % (__addon_id__, album_id), xbmc.LOGDEBUG)
                return None

            cover_url, timestamp = result
            current_time = int(time.time())
            cache_expire_seconds = self.get_cache_expire_seconds()

            # 检查是否过期
            if (current_time - timestamp) > cache_expire_seconds:
                xbmc.log('[%s] Album cover cache expired: %s' % (__addon_id__, album_id), xbmc.LOGDEBUG)
                self.delete_album_cover(album_id)
                return None

            xbmc.log('[%s] Album cover cache hit: %s' % (__addon_id__, album_id), xbmc.LOGDEBUG)
            return cover_url

        except Exception as e:
            xbmc.log('[%s] Error reading album cover cache: %s - %s' % (__addon_id__, album_id, str(e)), xbmc.LOGERROR)
            return None

    def set_album_cover(self, album_id, cover_url):
        """
        设置专辑封面 URL

        Args:
            album_id: 专辑 ID
            cover_url: 封面 URL

        Returns:
            bool: True 表示成功, False 表示失败
        """
        if not self.is_cache_enabled():
            return False

        try:
            timestamp = int(time.time())

            # 插入或更新
            self.cursor.execute('''
                INSERT OR REPLACE INTO album_covers (album_id, cover_url, timestamp)
                VALUES (?, ?, ?)
            ''', (album_id, cover_url, timestamp))
            self.conn.commit()

            xbmc.log('[%s] Album cover cached: %s' % (__addon_id__, album_id), xbmc.LOGDEBUG)
            return True

        except Exception as e:
            xbmc.log('[%s] Error caching album cover: %s - %s' % (__addon_id__, album_id, str(e)), xbmc.LOGERROR)
            return False

    def delete_album_cover(self, album_id):
        """
        删除指定专辑的封面缓存

        Args:
            album_id: 专辑 ID

        Returns:
            bool: True 表示成功, False 表示失败
        """
        try:
            self.cursor.execute('DELETE FROM album_covers WHERE album_id = ?', (album_id,))
            self.conn.commit()
            xbmc.log('[%s] Album cover cache deleted: %s' % (__addon_id__, album_id), xbmc.LOGDEBUG)
            return True
        except Exception as e:
            xbmc.log('[%s] Error deleting album cover cache: %s - %s' % (__addon_id__, album_id, str(e)), xbmc.LOGERROR)
            return False

    def clear_expired_album_covers(self):
        """
        清理过期的专辑封面缓存

        Returns:
            int: 删除的缓存数量
        """
        if not self.get_auto_clear_cache():
            return 0

        try:
            current_time = int(time.time())
            cache_expire_seconds = self.get_cache_expire_seconds()

            self.cursor.execute('''
                DELETE FROM album_covers
                WHERE (timestamp + ?) < ?
            ''', (cache_expire_seconds, current_time))
            deleted_count = self.cursor.rowcount
            self.conn.commit()
            xbmc.log('[%s] Cleared %d expired album covers' % (__addon_id__, deleted_count), xbmc.LOGINFO)
            return deleted_count
        except Exception as e:
            xbmc.log('[%s] Error clearing expired album covers: %s' % (__addon_id__, str(e)), xbmc.LOGERROR)
            return 0

    def get_stats(self):
        """
        获取缓存统计信息

        Returns:
            dict: 统计信息
        """
        try:
            # 总缓存数量
            self.cursor.execute('SELECT COUNT(*) FROM cache')
            total_count = self.cursor.fetchone()[0]

            # 按类型统计
            self.cursor.execute('''
                SELECT type, COUNT(*)
                FROM cache
                GROUP BY type
            ''')
            type_stats = dict(self.cursor.fetchall())

            # 过期缓存数量
            current_time = int(time.time())
            self.cursor.execute('''
                SELECT COUNT(*)
                FROM cache
                WHERE (timestamp + expire_seconds) < ?
            ''', (current_time,))
            expired_count = self.cursor.fetchone()[0]

            # 数据库大小
            db_size = os.path.getsize(CACHE_DB_PATH) if os.path.exists(CACHE_DB_PATH) else 0

            return {
                'total_count': total_count,
                'type_stats': type_stats,
                'expired_count': expired_count,
                'db_size': db_size
            }

        except Exception as e:
            xbmc.log('[%s] Error getting cache stats: %s' % (__addon_id__, str(e)), xbmc.LOGERROR)
            return {
                'total_count': 0,
                'type_stats': {},
                'expired_count': 0,
                'db_size': 0
            }

    # ==================== 播放历史记录方法 ====================

    def add_play_history(self, song_id, song_name, artist, artist_id, album, album_id, pic, duration):
        """
        添加播放历史记录

        Args:
            song_id: 歌曲ID
            song_name: 歌曲名称
            artist: 艺术家名称
            artist_id: 艺术家ID
            album: 专辑名称
            album_id: 专辑ID
            pic: 封面图片URL
            duration: 歌曲时长（秒）

        Returns:
            bool: 是否成功
        """
        try:
            play_time = int(time.time())
            self.cursor.execute('''
                INSERT OR REPLACE INTO play_history
                (song_id, song_name, artist, artist_id, album, album_id, pic, duration, play_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (song_id, song_name, artist, artist_id, album, album_id, pic, duration, play_time))
            self.conn.commit()
            xbmc.log('[%s] Play history added: %s - %s' % (__addon_id__, artist, song_name), xbmc.LOGDEBUG)
            return True
        except Exception as e:
            xbmc.log('[%s] Error adding play history: %s' % (__addon_id__, str(e)), xbmc.LOGERROR)
            return False

    def get_play_history(self, limit=None, days=None):
        """
        获取播放历史记录

        Args:
            limit: 限制返回数量，None 表示不限制
            days: 限制天数（最近N天），None 表示不限制

        Returns:
            list: 历史记录列表，每个元素为 dict
        """
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

            xbmc.log('[%s] Retrieved %d play history records' % (__addon_id__, len(history)), xbmc.LOGDEBUG)
            return history

        except Exception as e:
            xbmc.log('[%s] Error getting play history: %s' % (__addon_id__, str(e)), xbmc.LOGERROR)
            return []

    def clear_play_history(self):
        """
        清空播放历史记录

        Returns:
            bool: 是否成功
        """
        try:
            self.cursor.execute('DELETE FROM play_history')
            self.conn.commit()
            xbmc.log('[%s] Play history cleared' % __addon_id__, xbmc.LOGINFO)
            return True
        except Exception as e:
            xbmc.log('[%s] Error clearing play history: %s' % (__addon_id__, str(e)), xbmc.LOGERROR)
            return False

    def get_play_history_by_artist(self, artist):
        """
        获取指定艺术家的播放历史

        Args:
            artist: 艺术家名称

        Returns:
            list: 历史记录列表
        """
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

            xbmc.log('[%s] Retrieved %d play history records for artist: %s' % (__addon_id__, len(history), artist), xbmc.LOGDEBUG)
            return history

        except Exception as e:
            xbmc.log('[%s] Error getting play history by artist: %s' % (__addon_id__, str(e)), xbmc.LOGERROR)
            return []

    def get_play_history_by_album(self, album):
        """
        获取指定专辑的播放历史

        Args:
            album: 专辑名称

        Returns:
            list: 历史记录列表
        """
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

            xbmc.log('[%s] Retrieved %d play history records for album: %s' % (__addon_id__, len(history), album), xbmc.LOGDEBUG)
            return history

        except Exception as e:
            xbmc.log('[%s] Error getting play history by album: %s' % (__addon_id__, str(e)), xbmc.LOGERROR)
            return []

    def close(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()


def get_cached_data(prefix, *args):
    """
    便捷函数：从缓存读取数据

    Args:
        prefix: 缓存前缀
        *args: 缓存参数

    Returns:
        dict: 缓存数据, 或 None
    """
    cache_db = get_cache_db()
    cache_key = cache_db.generate_cache_key(prefix, *args)
    return cache_db.get(cache_key)


def set_cached_data(prefix, *args, **kwargs):
    """
    便捷函数：写入缓存数据

    Args:
        prefix: 缓存前缀
        *args: 缓存参数
        **kwargs: 其他参数 (data, cache_type, expire_seconds)

    Returns:
        bool: 是否成功
    """
    cache_db = get_cache_db()
    cache_key = cache_db.generate_cache_key(prefix, *args)
    return cache_db.set(cache_key, **kwargs)


# ==================== 播放历史记录管理 ====================

def add_play_history(song_id, song_name, artist, artist_id, album, album_id, pic, duration):
    """
    添加播放历史记录

    Args:
        song_id: 歌曲ID
        song_name: 歌曲名称
        artist: 艺术家名称
        artist_id: 艺术家ID
        album: 专辑名称
        album_id: 专辑ID
        pic: 封面图片URL
        duration: 歌曲时长（秒）

    Returns:
        bool: 是否成功
    """
    cache_db = get_cache_db()
    return cache_db.add_play_history(song_id, song_name, artist, artist_id, album, album_id, pic, duration)


def get_play_history(limit=None, days=None):
    """
    获取播放历史记录

    Args:
        limit: 限制返回数量，None 表示不限制
        days: 限制天数（最近N天），None 表示不限制

    Returns:
        list: 历史记录列表，每个元素为 dict
    """
    cache_db = get_cache_db()
    return cache_db.get_play_history(limit=limit, days=days)


def clear_play_history():
    """
    清空播放历史记录

    Returns:
        bool: 是否成功
    """
    cache_db = get_cache_db()
    return cache_db.clear_play_history()


def get_play_history_by_artist(artist):
    """
    获取指定艺术家的播放历史

    Args:
        artist: 艺术家名称

    Returns:
        list: 历史记录列表
    """
    cache_db = get_cache_db()
    return cache_db.get_play_history_by_artist(artist)


def get_play_history_by_album(album):
    """
    获取指定专辑的播放历史

    Args:
        album: 专辑名称

    Returns:
        list: 历史记录列表
    """
    cache_db = get_cache_db()
    return cache_db.get_play_history_by_album(album)
