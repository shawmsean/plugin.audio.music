# Kodi 音乐插件 - 代码架构文档

## 概述

这是一个基于 xbmcswift2 框架开发的 Kodi 音乐插件，主要集成网易云音乐 API，并额外支持 TuneHub 多平台音乐聚合服务。

## 目录结构

```
plugin.audio.music/
├── addon.py          # 主程序文件（路由、UI、播放逻辑）
├── api.py            # API 封装层（网易云、TuneHub）
└── README.md         # 本文档
```

---

## 核心架构

### 1. 初始化与配置

#### 导入与全局变量
```python
from api import NetEase
from xbmcswift2 import Plugin, xbmcgui, xbmcplugin, xbmc, xbmcaddon
import sqlite3, re, sys, hashlib, time, os, xbmcvfs, qrcode
from datetime import datetime
import json
```

#### 全局配置
- `plugin = Plugin()` - xbmcswift2 插件实例
- `music = NetEase()` - API 实例
- `account` - 用户账号存储（uid、logined、first_run）
- `limit` - 每页显示数量（默认 100）
- `level` - 音质设置（standard/higher/exhigh/lossless/hires 等）
- `resolution` - MV 分辨率（240/480/720/1080）

#### 存储管理
```python
def safe_get_storage(name, **kwargs):
    """安全获取持久化存储，失败时回退到内存字典"""
```

支持的存储类型：
- `liked_songs` - 喜欢的歌曲列表
- `account` - 账号信息
- `time_machine` - 黑胶时光机数据

---

### 2. 路由架构

插件使用 xbmcswift2 的装饰器路由系统，所有路由以 `@plugin.route()` 声明。

#### 2.1 主入口路由

| 路由 | 功能 | 说明 |
|------|------|------|
| `/` | index() | 主目录入口，显示所有功能模块 |
| `/login/` | login() | 手机号/邮箱登录 |
| `/logout/` | logout() | 退出登录 |
| `/qrcode_login/` | qrcode_login() | 二维码扫码登录 |

#### 2.2 播放相关路由

| 路由 | 功能 | 参数 |
|------|------|------|
| `/play/<meida_type>/<song_id>/<mv_id>/<sourceId>/<dt>/<source>/` | play() | 核心播放入口 |
| `/play_playlist_songs/<playlist_id>/<song_id>/<mv_id>/<dt>/` | play_playlist_songs() | 播放整张歌单 |
| `/play_recommend_songs/<song_id>/<mv_id>/<dt>/` | play_recommend_songs() | 播放每日推荐列表 |
| `/tunehub_play/<source>/<id>/<br>/` | tunehub_play() | TuneHub 播放入口 |

**设计原则**：所有音乐源统一走 `play()` 入口，确保播放行为一致。

#### 2.3 歌单与专辑路由

| 路由 | 功能 |
|------|------|
| `/playlist/<ptype>/<id>/` | playlist() | 显示歌单详情 |
| `/album/<id>/` | album() | 显示专辑详情 |
| `/user_playlists/<uid>/` | user_playlists() | 用户歌单列表 |
| `/recommend_playlists/` | recommend_playlists() | 推荐歌单 |
| `/hot_playlists/<offset>/` | hot_playlists() | 热门歌单 |

#### 2.4 歌手路由

| 路由 | 功能 |
|------|------|
| `/artist/<id>/` | artist() | 歌手详情页 |
| `/top_artists/` | top_artists() | 热门歌手 |
| `/artist_songs/<id>/<offset>/` | artist_songs() | 歌手所有歌曲 |
| `/hot_songs/<id>/` | hot_songs() | 歌手热门50首 |
| `/artist_mvs/<id>/<offset>/` | artist_mvs() | 歌手MV |
| `/similar_artist/<id>/` | similar_artist() | 相似歌手 |

#### 2.5 用户与社交路由

| 路由 | 功能 |
|------|------|
| `/user/<id>/` | user() | 用户主页 |
| `/user_getfollows/<uid>/<offset>/` | user_getfollows() | 关注列表 |
| `/user_getfolloweds/<uid>/<offset>/` | user_getfolloweds() | 粉丝列表 |
| `/follow_user/<type>/<id>/` | follow_user() | 关注/取消关注 |
| `/play_record/<uid>/` | play_record() | 听歌排行 |

#### 2.6 排行榜与推荐路由

| 路由 | 功能 |
|------|------|
| `/toplists/` | toplists() | 所有排行榜 |
| `/new_songs/` | new_songs() | 新歌速递 |
| `/new_albums/<offset>/` | new_albums() | 新碟上架 |
| `/recommend_songs/` | recommend_songs() | 每日推荐 |
| `/personal_fm/` | personal_fm() | 私人FM |
| `/vip_timemachine/` | vip_timemachine() | 黑胶时光机 |
| `/history_recommend_dates/` | history_recommend_dates() | 历史日推日期 |

#### 2.7 搜索路由

| 路由 | 功能 | type 参数 |
|------|------|-----------|
| `/search/` | search() | 搜索类型选择页 |
| `/sea/<type>/` | sea() | 执行搜索 |
|  | | 1=单曲, 10=专辑, 100=歌手, 1000=歌单 |
|  | | 1002=用户, 1004=MV, 1006=歌词 |
|  | | 1009=播客, 1014=视频, 1018=综合, -1=云盘 |

#### 2.8 TuneHub 路由（多平台聚合）

| 路由 | 功能 |
|------|------|
| `/tunehub_search/` | tunehub_search() | TuneHub 单平台搜索入口 |
| `/tunehub_search_platform/<source>/` | tunehub_search_platform() | 单平台搜索（网易云/QQ/酷我） |
| `/tunehub_aggregate_search/` | tunehub_aggregate_search() | TuneHub 聚合搜索 |
| `/tunehub_playlist/` | tunehub_playlist() | TuneHub 歌单入口 |
| `/tunehub_playlist_platform/<source>/` | tunehub_playlist_platform() | 单平台歌单 |
| `/tunehub_toplists/` | tunehub_toplists() | TuneHub 排行榜入口 |
| `/tunehub_toplists_platform/<source>/` | tunehub_toplists_platform() | 单平台排行榜 |
| `/tunehub_toplist/<source>/<id>/` | tunehub_toplist() | 排行榜详情 |

#### 2.9 收藏与云盘路由

| 路由 | 功能 |
|------|------|
| `/sublist/` | sublist() | 我的收藏（歌手/专辑/视频/播单/数字专辑） |
| `/cloud/<offset>/` | cloud() | 我的云盘 |
| `/artist_sublist/` | artist_sublist() | 收藏的歌手 |
| `/album_sublist/` | album_sublist() | 收藏的专辑 |
| `/video_sublist/` | video_sublist() | 收藏的视频 |
| `/song_purchased/<offset>/` | song_purchased() | 已购单曲 |
| `/digitalAlbum_purchased/` | digitalAlbum_purchased() | 数字专辑 |

#### 2.10 MV 与视频路由

| 路由 | 功能 |
|------|------|
| `/top_mvs/<offset>/` | top_mvs() | 热门MV |
| `/mlog_category/` | mlog_category() | Mlog 分类 |
| `/mlog/<cid>/<pagenum>/` | mlog() | Mlog 列表 |

#### 2.11 播放历史路由

| 路由 | 功能 |
|------|------|
| `/history/` | history() | 播放历史（全部） |
| `/history_filter/<filter>/` | history_filter() | 历史筛选（7天/30天） |
| `/history_by_artist/` | history_by_artist() | 按歌手分组 |
| `/history_by_album/` | history_by_album() | 按专辑分组 |
| `/history_group_artist/<artist>/` | history_group_artist() | 特定歌手历史 |
| `/history_group_album/<album>/` | history_group_album() | 特定专辑历史 |
| `/history_play_all/` | history_play_all() | 播放全部历史 |
| `/history_clear/` | history_clear() | 清空历史 |

#### 2.12 上下文菜单路由

| 路由 | 功能 |
|------|------|
| `/song_contextmenu/<action>/<meida_type>/<song_id>/<mv_id>/<sourceId>/<dt>/` | song_contextmenu() | 歌曲右键菜单 |
| `/playlist_contextmenu/<action>/<id>/` | playlist_contextmenu() | 歌单右键菜单 |
| `/to_artist/<artists>/` | to_artist() | 跳转到歌手页 |

#### 2.13 收藏夹路由（本地）

| 路由 | 功能 |
|------|------|
| `/favorite_toggle/<source>/<id>/<name>/<artist>/` | favorite_toggle() | 添加/取消收藏 |
| `/favorites/` | favorites() | 收藏夹列表 |

#### 2.14 其他功能路由

| 路由 | 功能 |
|------|------|
| `/delete_thumbnails/` | delete_thumbnails() | 删除缩略图缓存 |

---

### 3. 数据处理函数

#### 3.1 歌曲数据处理

```python
def get_songs(songs, privileges=[], picUrl=None, source=''):
    """
    将 API 返回的歌曲数据标准化为统一格式
    
    返回格式：
    {
        'id': int,
        'name': str,
        'artist': str,
        'artists': list,  # [[name, id], ...]
        'album_name': str,
        'album_id': int,
        'picUrl': str,
        'mv_id': int,
        'dt': int,        # 时长（毫秒）
        'disc': int,
        'no': int,
        'privilege': dict,# 播放权限信息
        'source': str     # 音乐源（netease/qq/kuwo 等）
    }
    """
```

**兼容性处理**：
- 支持多种嵌套结构（`song`、`simpleSong`、`songData`、`mainSong`）
- 兼容云盘歌曲（`simpleSong`）
- 处理歌词搜索（`source='search_lyric'`）

#### 3.2 歌曲列表项构建

```python
def get_songs_items(datas, privileges=[], picUrl=None, offset=0,
                    getmv=True, source='', sourceId=0, enable_index=True, widget='0'):
    """
    将标准化歌曲数据转换为 Kodi ListItem
    
    功能：
    - 构建播放列表项
    - 添加序号、标签（VIP、独家、SQ 等）
    - 处理上下文菜单
    - 根据 source 决定播放路径
    """
```

**关键逻辑**：
- **歌单页面**：在最前面插入"播放全部"按钮
- **推荐页面**：根据 widget 参数区分小部件和普通点击
- **播放路径选择**：
  - `source='recommend_songs'` → 播放推荐列表或单曲
  - `source='playlist'` → 直接指向 `play()` 路由
  - TuneHub 歌曲 → 指向 `tunehub_play()` 路由
  - 其他 → 指向 `play()` 路由

#### 3.3 其他数据转换函数

| 函数 | 功能 |
|------|------|
| `get_albums_items(albums)` | 专辑数据转换 |
| `get_artists_items(artists)` | 歌手数据转换 |
| `get_users_items(users)` | 用户数据转换 |
| `get_mvs_items(mvs)` | MV 数据转换 |
| `get_videos_items(videos)` | 视频数据转换 |
| `get_playlists_items(playlists)` | 歌单数据转换 |
| `get_djlists_items(playlists)` | 播客列表转换 |
| `get_dj_items(songs, sourceId)` | 播客节目转换 |

---

### 4. 播放系统

#### 4.1 核心播放函数

```python
@plugin.route('/play/<meida_type>/<song_id>/<mv_id>/<sourceId>/<dt>/<source>/')
def play(meida_type, song_id, mv_id, sourceId, dt, source='netease'):
    """
    统一播放入口
    
    参数：
    - meida_type: 'song' | 'mv' | 'dj' | 'mlog'
    - song_id: 歌曲/节目 ID
    - mv_id: MV/视频 ID
    - sourceId: 来源 ID（歌单 ID 等）
    - dt: 时长（秒）
    - source: 音乐源
    
    流程：
    1. 根据 meida_type 获取真实播放 URL
    2. 如果歌曲不可播放，尝试自动播放 MV
    3. 构建 ListItem 并设置元数据
    4. 记录播放历史
    5. 上传播放记录（如果启用）
    6. 调用 xbmcplugin.setResolvedUrl
    """
```

#### 4.2 播放列表播放

**歌单播放**：
```python
@plugin.route('/play_playlist_songs/<playlist_id>/<song_id>/<mv_id>/<dt>/')
def play_playlist_songs(playlist_id, song_id, mv_id, dt):
    """
    播放整张歌单
    
    采用"延迟解析"策略：
    1. 获取歌单详情和所有歌曲
    2. 构建 xbmc.PlayList，每项指向 play() 路由
    3. 播放器调用时才解析真实 URL
    4. 支持超过 1000 首的歌单
    """
```

**每日推荐播放**：
```python
@plugin.route('/play_recommend_songs/<song_id>/<mv_id>/<dt>/')
def play_recommend_songs(song_id, mv_id, dt):
    """
    播放每日推荐列表
    
    逻辑与 play_playlist_songs 相同
    """
```

#### 4.3 TuneHub 播放

```python
@plugin.route('/tunehub_play/<source>/<id>/<br>/')
def tunehub_play(source, id, br='320k'):
    """
    TuneHub 多平台播放入口
    
    流程：
    1. 调用 music.tunehub_url() 获取真实播放 URL
    2. 调用 music.tunehub_info() 获取元数据
    3. 构建 ListItem（使用 InfoTagMusic）
    4. 记录播放历史
    5. 调用 xbmcplugin.setResolvedUrl
    
    支持平台：netease、qq、kuwo
    """
```

---

### 5. 缓存系统

#### 5.1 歌词缓存（SQLite + LRU）

```python
def get_lrc_sqlite(source, track_id, ttl=86400, max_items=500):
    """
    获取歌词（带缓存）
    
    - 使用 SQLite 存储歌词
    - TTL：24 小时
    - LRU 策略：最多缓存 500 条
    - 清理最久未访问的记录
    """
```

**数据库结构**：
```sql
CREATE TABLE lrc_cache (
    source TEXT,
    track_id TEXT,
    text TEXT,
    time INTEGER,
    last_access INTEGER,
    PRIMARY KEY (source, track_id)
)
```

#### 5.2 封面缓存（本地文件）

```python
def get_cached_cover(url, max_size_mb=200, max_files=2000):
    """
    获取并缓存封面图片
    
    - 存储路径：addon_data/covers/
    - 文件名：MD5(url).jpg
    - 清理策略：
      - 最多 2000 个文件
      - 最大 200 MB
      - 按时间排序，删除最旧的
    """
```

#### 5.3 播放历史缓存

```python
def load_history():
    """加载播放历史（JSON 文件）"""

def save_history(history):
    """保存播放历史"""

# 历史记录格式：
{
    "id": int,
    "name": str,
    "artist": str,
    "artist_id": int,
    "album": str,
    "album_id": int,
    "pic": str,
    "dt": int,        # 时长（秒）
    "source": str,
    "time": int       # 播放时间戳
}
```

**历史记录功能**：
- 最多保存 1000 条
- 去重（同 ID 只保留最新）
- 支持按歌手/专辑分组
- 支持时间筛选（7天/30天）

---

### 6. 辅助功能

#### 6.1 工具函数

| 函数 | 功能 |
|------|------|
| `tag(info, color='red')` | 添加颜色标签 |
| `trans_num(num)` | 数字格式化（万/亿） |
| `trans_time(t)` | 时间戳转字符串 |
| `trans_date(t)` | 时间戳转日期 |
| `B2M(size)` | 字节转 MB |
| `delete_files(path)` | 递归删除文件 |
| `caculate_size(path)` | 计算目录大小 |

#### 6.2 二维码登录

```python
def qrcode_check():
    """检查并创建二维码目录"""

def check_login_status(key):
    """检查登录状态（轮询 10 次）"""

@plugin.route('/qrcode_login/')
def qrcode_login():
    """
    二维码登录流程：
    1. 获取 unikey
    2. 生成二维码图片
    3. 显示二维码
    4. 轮询检查登录状态
    """
```

#### 6.3 收藏夹（本地）

```python
@plugin.route('/favorite_toggle/<source>/<id>/<name>/<artist>/')
def favorite_toggle(source, id, name, artist):
    """添加/取消收藏（本地存储）"""

@plugin.route('/favorites/')
def favorites():
    """显示收藏夹"""
```

---

### 7. 数据库管理

```python
def get_db():
    """
    获取数据库连接
    
    数据库路径：addon_data/cache.db
    
    表结构：
    - lrc_cache: 歌词缓存
    - cover_cache: 封面缓存（预留）
    """
```

---

## 设计原则

### 1. 统一播放入口
所有音乐源通过 `play()` 路由统一处理，确保播放行为一致。

### 2. 延迟解析策略
歌单播放时，先构建播放列表，播放器调用时才解析真实 URL，提高响应速度。

### 3. 兼容性设计
- 支持多种 API 响应格式
- 处理嵌套数据结构（云盘、推荐等）
- 兼容不同平台的元数据字段

### 4. 缓存优化
- 歌词：SQLite + LRU
- 封面：本地文件 + 大小/数量限制
- 播放历史：JSON 文件 + 去重

### 5. 错误处理
- API 请求失败时提供友好的提示
- 播放失败时自动尝试 MV
- 使用 safe_get_storage 防止存储异常导致崩溃

---

## 配置项（Settings）

| 配置项 | 说明 |
|--------|------|
| `number_of_songs_per_page` | 每页显示歌曲数 |
| `quality` | 音质选择 |
| `resolution` | MV 分辨率 |
| `show_index` | 显示序号 |
| `show_album_name` | 显示专辑名 |
| `hide_songs` | 隐藏不可播放歌曲 |
| `hide_cover_songs` | 隐藏翻唱歌曲 |
| `like_tag` | 显示喜欢标签 |
| `vip_tag` | 显示 VIP 标签 |
| `cloud_tag` | 显示云盘标签 |
| `exclusive_tag` | 显示���家标签 |
| `sq_tag` | 显示 SQ 标签 |
| `presell_tag` | 显示预售标签 |
| `pay_tag` | 显示付费标签 |
| `mv_tag` | 显示 MV 标签 |
| `mvfirst` | MV 优先播放 |
| `auto_play_mv` | 歌曲不可播时自动播放 MV |
| `song_naming_format` | 歌曲命名格式 |
| `upload_play_record` | 上传播放记录 |
| `reverse_radio` | 播客倒序播放 |
| `daily_recommend` | 显示每日推荐 |
| `personal_fm` | 显示私人FM |
| `my_playlists` | 显示我的歌单 |
| `sublist` | 显示我的收藏 |
| `recommend_playlists` | 显示推荐歌单 |
| `vip_timemachine` | 显示黑胶时光机 |
| `rank` | 显示排行榜 |
| `hot_playlists` | 显示热门歌单 |
| `top_artist` | 显示热门歌手 |
| `top_mv` | 显示热门MV |
| `search` | 显示搜索 |
| `cloud_disk` | 显示云盘 |
| `home_page` | 显示主页 |
| `new_albums` | 显示新碟上架 |
| `mlog` | 显示 Mlog |
| `tunehub_search` | 显示 TuneHub 单平台搜索 |
| `tunehub_aggregate_search` | 显示 TuneHub 聚合搜索 |
| `tunehub_playlist` | 显示 TuneHub 歌单 |
| `tunehub_toplists` | 显示 TuneHub 排行榜 |

---

## 路由参数说明

### 核心播放参数
- `meida_type`: 媒体类型（song/mv/dj/mlog）
- `song_id`: 歌曲/节目 ID
- `mv_id`: MV/视频 ID
- `sourceId`: 来源 ID（歌单 ID 等）
- `dt`: 时长（秒）
- `source`: 音乐源（netease/qq/kuwo）
- `br`: 比特率（320k 等，TuneHub 专用）

### 分页参数
- `offset`: 偏移量（用于分页）

### 其他参数
- `ptype`: 歌单类型（normal/video）
- `type`: 搜索类型 / 关注类型
- `filter`: 历史筛选（7/30/all）
- `widget`: 小部件标记（0/1）
- `action`: 上下文菜单动作
- `uid`: 用户 ID
- `id`: 通用 ID
- `cid`: 分类 ID
- `pagenum`: 页码

---

## 更新日志

### 2026-01-23
- 整理代码架构文档
- 记录所有路由和函数

### 2026-01-10 ~ 2026-01-11
- 集成 TuneHub 多平台服务
- 实现延迟解析播放策略
- 优化播放历史功能
- 改进缓存系统

---

## 注意事项

1. **Python 版本兼容**：代码同时支持 Python 2 和 Python 3
2. **路径处理**：使用 `xbmcvfs.translatePath()` 处理跨平台路径
3. **存储安全**：使用 `safe_get_storage()` 防止存储异常
4. **日志记录**：关键操作都有日志输出，便于调试
5. **错误处理**：所有 API 调用都有 try-except 保护

---

## 扩展建议

1. **添加新音乐源**：在 `api.py` 中添加 API 方法，在 `addon.py` 中添加路由
2. **自定义播放列表**：扩展播放历史功能，支持创建自定义播放列表
3. **歌词显示**：集成 Kodi 歌词插件或内置歌词显示
4. **下载功能**：添加歌曲/MV 下载功能
5. **同步功能**：支持与其他音乐平台同步

---

## 参考资源

- [Kodi 插件开发文档](https://kodi.wiki/view/Add-on_development)
- [xbmcswift2 文档](https://github.com/jonathanandersson/xbmcswift2)
- [网易云音乐 API](https://github.com/Binaryify/NeteaseCloudMusicApi)
