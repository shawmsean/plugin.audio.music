# -*- coding: utf-8 -*-
import os
import time
import hashlib
import sqlite3
from api import NetEase
from xbmcswift2 import Plugin, xbmcgui, xbmcplugin, xbmc, xbmcaddon # type: ignore
import xbmcgui # type: ignore
import xbmcvfs # type: ignore

plugin = Plugin()

music = NetEase()
# =========================
# SQLite 缓存数据库
# =========================

def get_db():
    addon_data = xbmcvfs.translatePath(plugin.addon.getAddonInfo("profile"))
    if not xbmcvfs.exists(addon_data):
        xbmcvfs.mkdirs(addon_data)
    db_path = os.path.join(addon_data, "cache.db")

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lrc_cache (
            source TEXT,
            track_id TEXT,
            text TEXT,
            time INTEGER,
            last_access INTEGER,
            PRIMARY KEY (source, track_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cover_cache (
            url TEXT PRIMARY KEY,
            local_path TEXT,
            time INTEGER
        )
    """)
    conn.commit()
    return conn


# =========================
# 歌词缓存（SQLite + LRU）
# =========================

def get_lrc_sqlite(source, track_id, ttl=86400, max_items=500):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT text, time FROM lrc_cache WHERE source=? AND track_id=?", (source, track_id))
    row = cur.fetchone()

    # 命中缓存且未过期
    if row:
        text, t = row
        if time.time() - t < ttl:
            cur.execute(
                "UPDATE lrc_cache SET last_access=? WHERE source=? AND track_id=?",
                (int(time.time()), source, track_id)
            )
            conn.commit()
            return text

    # 调用 API 获取歌词
    try:
        resp = music.tunehub_api(source=source, id=track_id, type="lrc")
        text = resp.get("data") or ""
    except Exception:
        text = ""

    now = int(time.time())
    cur.execute(
        "REPLACE INTO lrc_cache (source, track_id, text, time, last_access) VALUES (?, ?, ?, ?, ?)",
        (source, track_id, text, now, now)
    )
    conn.commit()

    # LRU 清理
    _cleanup_lrc_sqlite(conn, max_items)

    return text


def _cleanup_lrc_sqlite(conn, max_items):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM lrc_cache")
    count = cur.fetchone()[0]
    if count <= max_items:
        return

    # 删除最久未访问的
    to_delete = count - max_items
    cur.execute(
        "SELECT source, track_id FROM lrc_cache ORDER BY last_access ASC LIMIT ?",
        (to_delete,)
    )
    rows = cur.fetchall()
    for source, track_id in rows:
        cur.execute("DELETE FROM lrc_cache WHERE source=? AND track_id=?", (source, track_id))
    conn.commit()


# =========================
# 封面缓存（本地文件 + 清理）
# =========================

def get_cached_cover(url, max_size_mb=200, max_files=2000):
    if not url:
        return ""

    addon_data = xbmcvfs.translatePath(plugin.addon.getAddonInfo("profile"))
    cover_dir = os.path.join(addon_data, "covers")
    if not xbmcvfs.exists(cover_dir):
        xbmcvfs.mkdirs(cover_dir)

    filename = hashlib.md5(url.encode("utf-8")).hexdigest() + ".jpg"
    local_path = os.path.join(cover_dir, filename)

    # 已缓存
    if xbmcvfs.exists(local_path):
        return local_path

    # 下载封面
    try:
        import requests
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            with xbmcvfs.File(local_path, "wb") as f:
                f.write(r.content)
        else:
            return url
    except Exception:
        return url

    # 清理缓存
    _cleanup_cover_cache(cover_dir, max_size_mb, max_files)

    return local_path


def _cleanup_cover_cache(cover_dir, max_size_mb, max_files):
    import glob

    files = glob.glob(os.path.join(cover_dir, "*.jpg"))
    if not files:
        return

    file_info = []
    total_size = 0

    for f in files:
        stat = xbmcvfs.Stat(f)
        size = stat.st_size()
        mtime = stat.st_mtime()
        total_size += size
        file_info.append((f, size, mtime))

    # 按时间排序（旧 → 新）
    file_info.sort(key=lambda x: x[2])

    # 按数量清理
    while len(file_info) > max_files:
        f, size, _ = file_info.pop(0)
        xbmcvfs.delete(f)
        total_size -= size

    # 按总大小清理
    max_bytes = max_size_mb * 1024 * 1024
    while total_size > max_bytes and file_info:
        f, size, _ = file_info.pop(0)
        xbmcvfs.delete(f)
        total_size -= size


# =========================
# 收藏夹（本地 storage）
# =========================

@plugin.route('/favorite_toggle/<source>/<id>/<name>/<artist>/')
def favorite_toggle(source, id, name, artist):
    storage = plugin.get_storage()
    favs = storage.get("favorites", [])

    exists = next((f for f in favs if f["id"] == id and f["source"] == source), None)

    if exists:
        favs = [f for f in favs if not (f["id"] == id and f["source"] == source)]
        xbmcgui.Dialog().notification("收藏夹", "已取消收藏：%s" % name, xbmcgui.NOTIFICATION_INFO, 2000)
    else:
        favs.append({
            "id": id,
            "source": source,
            "name": name,
            "artist": artist,
            "time": time.time()
        })
        xbmcgui.Dialog().notification("收藏夹", "已加入收藏：%s" % name, xbmcgui.NOTIFICATION_INFO, 2000)

    storage["favorites"] = favs
    plugin.redirect(plugin.request.referrer)


@plugin.route('/favorites/')
def favorites():
    storage = plugin.get_storage()
    favs = storage.get("favorites", [])

    items = []
    for f in favs:
        label = u"%s - %s [%s]" % (f["name"], f["artist"], f["source"])
        items.append({
            "label": label,
            "path": plugin.url_for("tunehub_play", source=f["source"], id=f["id"], br="320k"),
            "is_playable": False,
            "context_menu": [
                (
                    "取消收藏",
                    'RunPlugin(%s)' % plugin.url_for(
                        "favorite_toggle",
                        source=f["source"],
                        id=f["id"],
                        name=f["name"],
                        artist=f["artist"]
                    )
                )
            ]
        })

    if not items:
        xbmcgui.Dialog().notification("收藏夹", "暂无收藏", xbmcgui.NOTIFICATION_INFO, 2000)

    return items


# =========================
# TuneHub 榜单路由（最终版）
# =========================

@plugin.route('/tunehub_toplist/<source>/<id>/')
def tunehub_toplist(source, id):
    """
    TuneHub 榜单展示（最终版）
    - 分页 offset/limit
    - 排序 hot/duration
    - 多音质 br
    - 歌词预加载 + SQLite + LRU
    - 封面缓存 + 清理
    - 播放历史
    - 收藏夹右键菜单
    """


    # 参数
    offset = int(plugin.request.args.get("offset", [0])[0])
    limit = int(plugin.request.args.get("limit", [20])[0])
    sort_by = plugin.request.args.get("sort", ["hot"])[0]   # hot / duration
    br = plugin.request.args.get("br", ["320k"])[0]         # 128k / 320k / flac / flac24bit
    preload_lrc = plugin.request.args.get("lrc", ["0"])[0] == "1"

    storage = plugin.get_storage()

    # 缓存（列表级别，可选）
    cache_key = "toplist_%s_%s_%d_%d_%s_%s_%d" % (source, id, offset, limit, sort_by, br, int(preload_lrc))
    cache_ttl = 3600
    cached = storage.get(cache_key)
    if cached and time.time() - cached["time"] < cache_ttl:
        plugin.log("[TuneHub] 使用缓存 toplist %s/%s offset=%d" % (source, id, offset))
        return cached["items"]

    # 调用 API
    try:
        resp = music.tunehub_toplist(source, id, offset=offset, limit=limit)
    except Exception as e:
        plugin.log("[TuneHub] API 调用失败: %s" % e, level=plugin.LOGERROR)
        xbmcgui.Dialog().notification("TuneHub", "排行榜加载失败", xbmcgui.NOTIFICATION_ERROR, 3000)
        return []

    data = resp.get("data") if isinstance(resp, dict) else resp
    if isinstance(data, dict):
        tracks = data.get("tracks") or data.get("list") or data.get("data") or []
    elif isinstance(data, list):
        tracks = data
    else:
        tracks = []

    # 排序
    if sort_by == "duration":
        tracks.sort(key=lambda x: x.get("duration") or x.get("dt") or 0)
    else:
        tracks.sort(key=lambda x: x.get("score") or x.get("hot") or 0, reverse=True)

    favs = storage.get("favorites", [])
    items = []
    history = storage.get("history", [])

    for it in tracks:
        name = it.get("name") or it.get("title") or ""
        artist = it.get("artist") or it.get("artistName") or ""
        album = it.get("album") or it.get("albumName") or ""
        duration = it.get("duration") or it.get("dt") or 0
        platform = it.get("platform") or it.get("source") or source

        pic = (
            it.get("pic") or it.get("picUrl") or it.get("cover") or
            it.get("image") or it.get("thumbnail") or it.get("thumb") or ""
        )

        pid = it.get("id")
        url = it.get("url")

        # 歌词预加载（可选）
        if preload_lrc and pid:
            lrc_text = get_lrc_sqlite(platform, str(pid))
        else:
            lrc_text = ""

        # 播放路径
        if pid:
            path = plugin.url_for(
                "tunehub_play",
                source=platform,
                id=pid,
                br=br,
                lrc="1" if preload_lrc else "0"
            )
            is_playable = False
        else:
            path = url
            is_playable = True

        # 封面缓存
        cover = get_cached_cover(pic) if pic else ""

        # 收藏状态
        is_fav = any(f["id"] == str(pid) and f["source"] == platform for f in favs) if pid else False

        label = u"%s - %s [%s]" % (name, artist, platform)
        if is_fav:
            label = u"★ " + label

        item = {
            "label": label,
            "path": path,
            "is_playable": is_playable,
            "thumbnail": cover,
            "icon": cover,
            "fanart": cover,
            "info": {
                "title": name,
                "artist": artist,
                "album": album,
                "duration": duration // 1000 if duration > 1000 else duration,
                "mediatype": "song",
            },
            "properties": {
                "lrc": lrc_text
            }
        }

        # 右键菜单：收藏 / 取消收藏
        if pid:
            item["context_menu"] = [
                (
                    "取消收藏" if is_fav else "加入收藏",
                    'RunPlugin(%s)' % plugin.url_for(
                        "favorite_toggle",
                        source=platform,
                        id=str(pid),
                        name=name,
                        artist=artist
                    )
                )
            ]

        items.append(item)

        # 播放历史记录（按列表加入）
        history.append({
            "title": name,
            "artist": artist,
            "source": platform,
            "id": str(pid) if pid else "",
            "time": time.time()
        })

    # 历史保留最近 200 条
    storage["history"] = history[-200:]

    # 分页：下一页
    next_offset = offset + limit
    items.append({
        "label": u"下一页 → (offset=%d)" % next_offset,
        "path": plugin.url_for(
            "tunehub_toplist",
            source=source,
            id=id,
            offset=next_offset,
            limit=limit,
            sort=sort_by,
            br=br,
            lrc="1" if preload_lrc else "0"
        )
    })

    # 列表缓存
    storage[cache_key] = {"time": time.time(), "items": items}

    plugin.log("[TuneHub] 成功加载 toplist %s/%s offset=%d, count=%d" % (source, id, offset, len(items)))

    return items
