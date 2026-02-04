# -*- coding:utf-8 -*-
import json
import os
import sys
import time
import requests
import re
import hashlib
from urllib.parse import urlparse, urlencode
from encrypt import encrypted_request
from xbmcswift2 import xbmc, xbmcaddon, xbmcplugin # type: ignore
from http.cookiejar import Cookie
from http.cookiejar import MozillaCookieJar
import xbmcvfs # pyright: ignore[reportMissingImports]
try:
    xbmc.translatePath = xbmcvfs.translatePath
except AttributeError:
    pass

# 导入缓存模块
try:
    from cache import get_cache_db
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    xbmc.log('[plugin.audio.music] Cache module not available', xbmc.LOGWARNING)

DEFAULT_TIMEOUT = 10

BASE_URL = "https://music.163.com"
TUNEHUB_API = "https://music-dl.sayqz.com/api/"

# LXMUSIC API 配置
LXMUSIC_API_URL = 'https://88.lxmusic.xn--fiqs8s'
LXMUSIC_API_KEY = 'lxmusic'
LXMUSIC_SECRET_KEY = 'JaJ?a7Nwk_Fgj?2o:znAkst'
LXMUSIC_SCRIPT_MD5 = '1888f9865338afe6d5534b35171c61a4'
LXMUSIC_VERSION = 4

# LXMUSIC 音源映射
LXMUSIC_SOURCE_MAPPING = {
    'netease': 'wy',
    'tencent': 'tx',
    'migu': 'mg',
    'kugou': 'kg',
    'kuwo': 'kw',
    'joox': 'jm',
    'deezer': 'dp',
    'ximalaya': 'xm',
    'apple': 'ap',
    'spotify': 'sp',
    'ytmusic': 'yt',
    'qobuz': 'qd',
    'tidal': 'td'
}

# GD Music API 配置
GD_MUSIC_API_URL = 'https://music-api.gdstudio.xyz/api.php'
# GD Music API 支持的音源
GD_MUSIC_SOURCES = ['netease', 'kuwo'] #'joox', 'tencent', 'tidal', 'spotify', 'ytmusic', 'qobuz', 'deezer', 'migu', 'kugou', 'ximalaya', 'apple']

# 搜索 API 配置
SEARCH_API_URL = 'https://music-api.gdstudio.xyz/api.php'
# 搜索 API 支持的音源（与 LXMUSIC 映射对应）
SEARCH_API_SOURCES = ['kuwo', 'netease']#, 'tencent', 'migu', 'kugou']

PROFILE = xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
if not os.path.exists(PROFILE):
    os.makedirs(PROFILE)
COOKIE_PATH = os.path.join(PROFILE, 'cookie.txt')
if not os.path.exists(COOKIE_PATH):
    with open(COOKIE_PATH, 'w') as f:
        f.write('# Netscape HTTP Cookie File\n')


class NetEase(object):
    def __init__(self):
        self.header = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip,deflate,sdch",
            "Accept-Language": "zh-CN,zh;q=0.8,gl;q=0.6,zh-TW;q=0.4",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "music.163.com",
            "Referer": "http://music.163.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36",
        }

        cookie_jar = MozillaCookieJar(COOKIE_PATH)
        cookie_jar.load()
        self.session = requests.Session()
        self.session.cookies = cookie_jar

        for cookie in cookie_jar:
            if cookie.is_expired():
                cookie_jar.clear()
                break

        self.enable_proxy = False
        if xbmcplugin.getSetting(int(sys.argv[1]), 'enable_proxy') == 'true':
            self.enable_proxy = True
            proxy = xbmcplugin.getSetting(int(sys.argv[1]), 'host').strip(
            ) + ':' + xbmcplugin.getSetting(int(sys.argv[1]), 'port').strip()
            self.proxies = {
                'http': 'http://' + proxy,
                'https': 'https://' + proxy,
            }

    def _raw_request(self, method, endpoint, data=None, use_mobile_header=False):
        """发送原始 HTTP 请求

        Args:
            method: HTTP 方法 (GET/POST)
            endpoint: 请求端点
            data: 请求参数
            use_mobile_header: 是否使用移动端请求头（用于扫码登录等）
        """
        headers = self._get_mobile_header() if use_mobile_header else self.header

        if method == "GET":
            if not self.enable_proxy:
                resp = self.session.get(
                    endpoint, params=data, headers=headers, timeout=DEFAULT_TIMEOUT
                )
            else:
                resp = self.session.get(
                    endpoint, params=data, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=self.proxies
                )
        elif method == "POST":
            if not self.enable_proxy:
                resp = self.session.post(
                    endpoint, data=data, headers=headers, timeout=DEFAULT_TIMEOUT
                )
            else:
                resp = self.session.post(
                    endpoint, data=data, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=self.proxies
                )
        return resp

    def _get_mobile_header(self):
        """获取移动端请求头（模拟 Android 客户端）"""
        return {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "music.163.com",
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36 NeteaseMusic/9.2.70",
            "Referer": "https://music.163.com/",
        }

    # 生成Cookie对象
    def make_cookie(self, name, value):
        return Cookie(
            version=0,
            name=name,
            value=value,
            port=None,
            port_specified=False,
            domain="music.163.com",
            domain_specified=True,
            domain_initial_dot=False,
            path="/",
            path_specified=True,
            secure=False,
            expires=None,
            discard=False,
            comment=None,
            comment_url=None,
            rest={},
        )

    def request(self, method, path, params={}, default={"code": -1}, custom_cookies={'os': 'android', 'appver': '9.2.70'}, use_mobile_header=False):
        """发送 API 请求

        Args:
            method: HTTP 方法 (GET/POST)
            path: API 路径
            params: 请求参数
            default: 默认返回值
            custom_cookies: 自定义 Cookie
            use_mobile_header: 是否使用移动端请求头（用于扫码登录等）
        """
        endpoint = "{}{}".format(BASE_URL, path)
        csrf_token = ""
        for cookie in self.session.cookies:
            if cookie.name == "__csrf":
                csrf_token = cookie.value
                break
        params.update({"csrf_token": csrf_token})
        data = default

        for key, value in custom_cookies.items():
            cookie = self.make_cookie(key, value)
            self.session.cookies.set_cookie(cookie)

        params = encrypted_request(params)
        try:
            resp = self._raw_request(method, endpoint, params, use_mobile_header=use_mobile_header)
            data = resp.json()
        except requests.exceptions.RequestException as e:
            print(e)
        except ValueError as e:
            print("Path: {}, response: {}".format(path, resp.text[:200]))
        finally:
            return data

    def login(self, username, password):
        if username.isdigit():
            path = "/weapi/login/cellphone"
            params = dict(phone=username, password=password,
                          rememberLogin="true")
        else:
            # magic token for login
            # see https://github.com/Binaryify/NeteaseCloudMusicApi/blob/master/router/login.js#L15
            client_token = (
                "1_jVUMqWEPke0/1/Vu56xCmJpo5vP1grjn_SOVVDzOc78w8OKLVZ2JH7IfkjSXqgfmh"
            )
            path = "/weapi/login"
            params = dict(
                username=username,
                password=password,
                rememberLogin="true",
                clientToken=client_token,
            )
        data = self.request("POST", path, params)
        # 保存cookie
        self.session.cookies.save()
        return data

    # 每日签到
    def daily_task(self, is_mobile=True):
        path = "/weapi/point/dailyTask"
        params = dict(type=0 if is_mobile else 1)
        return self.request("POST", path, params)

    # 用户歌单
    def user_playlist(self, uid, offset=0, limit=1000, includeVideo=True):
        path = "/weapi/user/playlist"
        params = dict(uid=uid, offset=offset, limit=limit,
                      includeVideo=includeVideo, csrf_token="")
        return self.request("POST", path, params)
        # specialType:5 喜欢的歌曲; 200 视频歌单; 0 普通歌单

    # 每日推荐歌单
    def recommend_resource(self, use_cache=True):
        """
        获取推荐资源

        Args:
            use_cache: 是否使用缓存 (默认 True)

        Returns:
            dict: 推荐资源数据
        """
        # 尝试从缓存读取
        if use_cache and CACHE_AVAILABLE:
            cache_db = get_cache_db()
            cached_data = cache_db.get('recommend_resource')
            if cached_data is not None:
                xbmc.log('[plugin.audio.music] Using cached recommend_resource', xbmc.LOGDEBUG)
                return cached_data

        # 从 API 获取数据
        path = "/weapi/v1/discovery/recommend/resource"
        result = self.request("POST", path)

        # 写入缓存
        if use_cache and CACHE_AVAILABLE and result:
            cache_db = get_cache_db()
            cache_db.set('recommend_resource', result, cache_type='recommend_resource')

        return result

    # 每日推荐歌曲
    def recommend_playlist(self, total=True, offset=0, limit=20):
        path = "/weapi/v3/discovery/recommend/songs"
        params = dict(total=total, offset=offset, limit=limit, csrf_token="")
        return self.request("POST", path, params)

    # 获取历史日推可用日期
    def history_recommend_recent(self):
        path = "/weapi/discovery/recommend/songs/history/recent"
        return self.request("POST", path)

    # 获取历史日推
    def history_recommend_detail(self, date=''):
        path = "/weapi/discovery/recommend/songs/history/detail"
        params = dict(date=date)
        return self.request("POST", path, params)

    # 私人FM
    def personal_fm(self):
        path = "/weapi/v1/radio/get"
        return self.request("POST", path)

    # 搜索单曲(1)，歌手(100)，专辑(10)，歌单(1000)，用户(1002)，歌词(1006)，主播电台(1009)，MV(1004)，视频(1014)，综合(1018) *(type)*
    def search(self, keywords, stype=1, offset=0, total="true", limit=100):
        path = "/weapi/search/get"
        params = dict(s=keywords, type=stype, offset=offset,
                      total=total, limit=limit)
        return self.request("POST", path, params)

    # 新碟上架
    def new_albums(self, offset=0, limit=50, use_cache=True):
        """
        获取新碟上架

        Args:
            offset: 偏移量
            limit: 每页数量
            use_cache: 是否使用缓存 (默认 True)

        Returns:
            dict: 新碟数据
        """
        # 尝试从缓存读取
        if use_cache and CACHE_AVAILABLE:
            cache_db = get_cache_db()
            cache_key = cache_db.generate_cache_key('new_albums', offset, limit)
            cached_data = cache_db.get(cache_key)
            if cached_data is not None:
                xbmc.log('[plugin.audio.music] Using cached new_albums', xbmc.LOGDEBUG)
                return cached_data

        # 从 API 获取数据
        path = "/weapi/album/new"
        params = dict(area="ALL", offset=offset, total=True, limit=limit)
        result = self.request("POST", path, params)

        # 写入缓存
        if use_cache and CACHE_AVAILABLE and result:
            cache_db = get_cache_db()
            cache_db.set(cache_key, result, cache_type='new_albums')

        return result

    # 歌单（网友精选碟） hot||new http://music.163.com/#/discover/playlist/
    def top_playlists(self, category="全部", order="hot", offset=0, limit=50):
        path = "/weapi/playlist/list"
        params = dict(
            cat=category, order=order, offset=offset, total="true", limit=limit
        )
        return self.request("POST", path, params)
    
        # 歌单（网友精选碟） hot||new http://music.163.com/#/discover/playlist/
    def hot_playlists(self, category="全部", order="hot", offset=0, limit=50, use_cache=True):
        """
        获取热门歌单

        Args:
            category: 分类标签
            order: 排序方式
            offset: 偏移量
            limit: 每页数量
            use_cache: 是否使用缓存 (默认 True)

        Returns:
            dict: 歌单数据
        """
        # 尝试从缓存读取
        if use_cache and CACHE_AVAILABLE:
            cache_db = get_cache_db()
            cache_key = cache_db.generate_cache_key('hot_playlists', category, order, offset, limit)
            cached_data = cache_db.get(cache_key)
            if cached_data is not None:
                xbmc.log('[plugin.audio.music] Using cached hot_playlists: %s' % category, xbmc.LOGDEBUG)
                return cached_data

        # 从 API 获取数据
        path = "/weapi/playlist/list"
        params = dict(
            cat=category, order=order, offset=offset, total="true", limit=limit
        )
        result = self.request("POST", path, params)

        # 写入缓存
        if use_cache and CACHE_AVAILABLE and result:
            cache_db = get_cache_db()
            cache_db.set(cache_key, result, cache_type='hot_playlists')

        return result

    def playlist_catelogs(self, use_cache=True):
        """
        获取歌单分类标签

        Args:
            use_cache: 是否使用缓存 (默认 True)

        Returns:
            dict: 分类标签数据
        """
        # 尝试从缓存读取
        if use_cache and CACHE_AVAILABLE:
            cache_db = get_cache_db()
            cached_data = cache_db.get('playlist_catelogs')
            if cached_data is not None:
                xbmc.log('[plugin.audio.music] Using cached playlist_catelogs', xbmc.LOGDEBUG)
                return cached_data

        # 从 API 获取数据
        path = "/weapi/playlist/catalogue"
        result = self.request("POST", path)

        # 写入缓存
        if use_cache and CACHE_AVAILABLE and result:
            cache_db = get_cache_db()
            cache_db.set('playlist_catelogs', result, cache_type='playlist_catelogs')

        return result

    # 歌单详情
    def playlist_detail(self, id, shareUserId=0, use_cache=True):
        """
        获取歌单详情

        Args:
            id: 歌单 ID
            shareUserId: 分享用户 ID
            use_cache: 是否使用缓存 (默认 True)

        Returns:
            dict: 歌单详情数据
        """
        # 尝试从缓存读取
        if use_cache and CACHE_AVAILABLE:
            cache_db = get_cache_db()
            cache_key = cache_db.generate_cache_key('playlist_detail', id)
            cached_data = cache_db.get(cache_key)
            if cached_data is not None:
                xbmc.log('[plugin.audio.music] Using cached playlist_detail: %s' % id, xbmc.LOGDEBUG)
                return cached_data

        # 从 API 获取数据
        path = "/weapi/v6/playlist/detail"
        params = dict(id=id, t=int(time.time()), n=1000,
                      s=5, shareUserId=shareUserId)
        result = self.request("POST", path, params)

        # 写入缓存
        if use_cache and CACHE_AVAILABLE and result:
            cache_db = get_cache_db()
            cache_db.set(cache_key, result, cache_type='playlist_detail')

        return result

    # 热门歌手 http://music.163.com/#/discover/artist/
    def top_artists(self, offset=0, limit=100, total=True, use_cache=True):
        """
        获取热门歌手

        Args:
            offset: 偏移量
            limit: 每页数量
            total: 是否获取总数
            use_cache: 是否使用缓存 (默认 True)

        Returns:
            dict: 热门歌手数据
        """
        # 尝试从缓存读取
        if use_cache and CACHE_AVAILABLE:
            cache_db = get_cache_db()
            cache_key = cache_db.generate_cache_key('top_artists', offset, limit, total)
            cached_data = cache_db.get(cache_key)
            if cached_data is not None:
                xbmc.log('[plugin.audio.music] Using cached top_artists', xbmc.LOGDEBUG)
                return cached_data

        # 从 API 获取数据
        path = "/weapi/artist/top"
        params = dict(offset=offset, total=total, limit=limit)
        result = self.request("POST", path, params)

        # 写入缓存
        if use_cache and CACHE_AVAILABLE and result:
            cache_db = get_cache_db()
            cache_db.set(cache_key, result, cache_type='top_artists')

        return result

    # 歌手单曲
    def artists(self, artist_id):
        path = "/weapi/v1/artist/{}".format(artist_id)
        return self.request("POST", path)

    def artist_album(self, artist_id, offset=0, limit=50):
        path = "/weapi/artist/albums/{}".format(artist_id)
        params = dict(offset=offset, total=True, limit=limit)
        return self.request("POST", path, params)

    # album id --> song id set
    def album(self, album_id):
        path = "/weapi/v1/album/{}".format(album_id)
        return self.request("POST", path)

    def song_comments(self, music_id, offset=0, total="false", limit=100):
        path = "/weapi/v1/resource/comments/R_SO_4_{}/".format(music_id)
        params = dict(rid=music_id, offset=offset, total=total, limit=limit)
        return self.request("POST", path, params)

    # song ids --> song urls ( details )
    def songs_detail(self, ids):
        path = "/weapi/v3/song/detail"
        params = dict(c=json.dumps([{"id": _id}
                      for _id in ids]), ids=json.dumps(ids))
        return self.request("POST", path, params)

    def songs_url(self, ids, bitrate, source='netease'):
        path = "/weapi/song/enhance/player/url"
        params = dict(ids=ids, br=bitrate)

        # 先使用 TuneHub 逐条获取播放地址，缺失的再回退到网易云原接口
        try:
            # 规范化 ids 为列表
            if isinstance(ids, str):
                try:
                    ids_list = json.loads(ids)
                except Exception:
                    if ids.startswith('[') and ids.endswith(']'):
                        ids_list = [ids]
                    else:
                        ids_list = [ids]
            elif isinstance(ids, list):
                ids_list = ids
            else:
                ids_list = [ids]
        except Exception:
            ids_list = [ids]

        xbmc.log("plugin.audio.music: songs_url ids_list={}".format(ids_list), xbmc.LOGDEBUG)
        result_data = []
        missing_ids = []
        for _id in ids_list:
            url = None
            try:
                xbmc.log("plugin.audio.music: songs_url trying TuneHub id={} br={}".format(_id, bitrate), xbmc.LOGDEBUG)
                tun = self.tunehub_url(_id, br=bitrate, source=source)
                xbmc.log("plugin.audio.music: songs_url tunehub raw for id={} -> {}".format(_id, tun), xbmc.LOGDEBUG)
                if isinstance(tun, dict):
                    if 'url' in tun:
                        url = tun.get('url')
                    elif 'data' in tun:
                        d = tun.get('data')
                        if isinstance(d, dict):
                            url = d.get('url')
                        elif isinstance(d, list) and len(d) > 0:
                            url = d[0].get('url') if isinstance(d[0], dict) else None
                elif isinstance(tun, str):
                    url = tun
            except Exception as e:
                xbmc.log("plugin.audio.music: songs_url tunehub exception id={} err={}".format(_id, e), xbmc.LOGERROR)
                url = None

            xbmc.log("plugin.audio.music: songs_url tunehub resolved id={} url={}".format(_id, url), xbmc.LOGDEBUG)
            result_data.append({'id': _id, 'url': url, 'br': bitrate})
            if not url:
                missing_ids.append(_id)

        # 如果有缺失的 id，则调用原接口批量请求并合并回填
        if missing_ids:
            xbmc.log("plugin.audio.music: songs_url missing_ids after TuneHub: {}".format(missing_ids), xbmc.LOGDEBUG)
            try:
                xbmc.log("plugin.audio.music: songs_url falling back to NetEase for ids {}".format(missing_ids), xbmc.LOGDEBUG)
                # 传入的 ids 参数在原接口可以是列表或json字符串，保持与传入一致
                netease_params = dict(ids=missing_ids if isinstance(ids, (list, tuple)) else json.dumps(missing_ids), br=bitrate)
                netease_data = self.request("POST", path, netease_params)
                xbmc.log("plugin.audio.music: songs_url netease response type={}".format(type(netease_data)), xbmc.LOGDEBUG)
                if isinstance(netease_data, dict) and 'data' in netease_data:
                    for item in netease_data.get('data') or []:
                        nid = item.get('id')
                        nurl = item.get('url')
                        # 找到对应的 result_data 条目并回填
                        for rd in result_data:
                            try:
                                if str(rd.get('id')) == str(nid) and (not rd.get('url')) and nurl:
                                    rd['url'] = nurl
                                    if 'br' in item:
                                        rd['br'] = item.get('br')
                                    xbmc.log("plugin.audio.music: songs_url backfilled id={} url={}".format(nid, nurl), xbmc.LOGDEBUG)
                                    break
                            except Exception:
                                continue
            except Exception as e:
                xbmc.log("plugin.audio.music: songs_url netease fallback failed: {}".format(e), xbmc.LOGERROR)
                pass

        return {'data': result_data}

    def songs_url_v1(self, ids, level, source='netease', song_names=None, artist_names=None):
        """
        获取歌曲播放链接（带智能搜索回退）

        Args:
            ids: 歌曲ID列表或单个ID
            level: 音质级别 (standard/exceed/high/lossless/hires/dolby/jyeffect/jymaster)
            source: 音源 (netease/tencent/migu/kugou/kuwo/joox/deezer/ximalaya/apple/spotify/ytmusic/qobuz/tidal)
            song_names: 歌曲名称列表（用于搜索回退）
            artist_names: 歌手名称列表（用于搜索回退）

        Returns:
            {'data': [{'id': id, 'url': url, 'level': level, 'source': source}]}
        """
        path = "/weapi/song/enhance/player/url/v1"

        # 解析 ids 参数
        try:
            if isinstance(ids, str):
                try:
                    ids_list = json.loads(ids)
                except Exception:
                    if ids.startswith('[') and ids.endswith(']'):
                        ids_list = [ids]
                    else:
                        ids_list = [ids]
            elif isinstance(ids, list):
                ids_list = ids
            else:
                ids_list = [ids]
        except Exception:
            ids_list = [ids]

        xbmc.log("plugin.audio.music: songs_url_v1 ids_list={} level={} source={}".format(ids_list, level, source), xbmc.LOGDEBUG)
        result_data = []
        missing_ids = []

        # 获取 LXMUSIC 音源标识符
        lxmusic_source = LXMUSIC_SOURCE_MAPPING.get(source)
        quality = self._convert_level_to_quality(level)

        xbmc.log("plugin.audio.music: LXMUSIC source mapping: {} -> {}, quality: {} -> {}".format(
            source, lxmusic_source, level, quality), xbmc.LOGDEBUG)

        # 处理歌曲名称和歌手名称（用于搜索回退）
        if isinstance(song_names, str):
            song_names = [song_names]
        elif song_names is None:
            song_names = [None] * len(ids_list)

        if isinstance(artist_names, str):
            artist_names = [artist_names]
        elif artist_names is None:
            artist_names = [None] * len(ids_list)

        for idx, _id in enumerate(ids_list):
            url = None
            used_source = None
            song_name = song_names[idx] if idx < len(song_names) else None
            artist_name = artist_names[idx] if idx < len(artist_names) else None

            # 1. 如果 source 支持,优先使用 LXMUSIC API
            if lxmusic_source:
                try:
                    xbmc.log("plugin.audio.music: songs_url_v1 trying LXMUSIC id={} source={}".format(_id, lxmusic_source), xbmc.LOGDEBUG)
                    url = self._lxmusic_get_music_url(lxmusic_source, str(_id), quality)

                    if url:
                        # 检查 URL 是否可用
                        if self._check_url_valid(url):
                            used_source = 'lxmusic'
                            xbmc.log("plugin.audio.music: songs_url_v1 LXMUSIC success id={} url={}".format(_id, url), xbmc.LOGDEBUG)
                        else:
                            xbmc.log("plugin.audio.music: songs_url_v1 LXMUSIC URL不可用 id={}".format(_id), xbmc.LOGWARNING)
                            url = None
                except Exception as e:
                    xbmc.log("plugin.audio.music: songs_url_v1 LXMUSIC failed id={} error={}".format(_id, str(e)), xbmc.LOGWARNING)
                    url = None

                # 1.5. 如果 LXMUSIC 返回的链接不可用，尝试搜索回退
                if not url and (song_name or artist_name):
                    xbmc.log("plugin.audio.music: songs_url_v1 尝试搜索回退 id={} song_name={} artist_name={}".format(
                        _id, song_name, artist_name), xbmc.LOGDEBUG)
                    url = self._search_and_retry_lxmusic(str(_id), song_name, artist_name, lxmusic_source, quality)
                    
                    if url:
                        used_source = 'lxmusic_search'

            # 2. 如果 LXMUSIC 失败或 source 是 netease，尝试 GD Music API
            if not url:
                try:
                    xbmc.log("plugin.audio.music: songs_url_v1 trying GD Music API id={}".format(_id), xbmc.LOGDEBUG)
                    # 将 level 转换为 GD Music API 支持的音质格式
                    gd_quality = self._convert_level_to_gdmusic_quality(level)
                    play_url, actual_source = self._gdmusic_get_play_url_with_fallback(
                        str(_id), quality=gd_quality, song_name=song_name, artist_name=artist_name, original_source=source
                    )

                    if play_url:
                        url = play_url
                        used_source = 'gdmusic_%s' % actual_source
                        xbmc.log("plugin.audio.music: songs_url_v1 GD Music success id={} url={} source={}".format(_id, url, actual_source), xbmc.LOGDEBUG)
                    else:
                        xbmc.log("plugin.audio.music: songs_url_v1 GD Music failed id={}".format(_id), xbmc.LOGWARNING)
                except Exception as e:
                    xbmc.log("plugin.audio.music: songs_url_v1 GD Music failed id={} error={}".format(_id, str(e)), xbmc.LOGWARNING)
                    url = None

            # 2.5. 如果 GD Music 也失败，且支持搜索回退，尝试搜索回退
            if not url and lxmusic_source:
                xbmc.log("plugin.audio.music: songs_url_v1 GD Music失败，尝试搜索回退 id={}".format(_id), xbmc.LOGDEBUG)
                url = self._search_and_retry_lxmusic(str(_id), song_name, artist_name, lxmusic_source, quality)
                if url:
                    used_source = 'lxmusic_search_after_gdmusic'

            xbmc.log("plugin.audio.music: songs_url_v1 id={} url={} used_source={}".format(_id, url, used_source), xbmc.LOGDEBUG)
            result_data.append({'id': _id, 'url': url, 'level': level, 'source': used_source})

            if not url:
                missing_ids.append(_id)

        # 回退网易原始接口以获取剩余的播放地址
        if missing_ids:
            xbmc.log("plugin.audio.music: songs_url_v1 missing_ids after LXMUSIC/TuneHub: {}".format(missing_ids), xbmc.LOGDEBUG)
            try:
                if level == 'dolby':
                    netease_params = dict(ids=missing_ids if isinstance(ids, (list, tuple)) else json.dumps(missing_ids), level='hires', effects='["dolby"]', encodeType='mp4')
                    xbmc.log("plugin.audio.music: songs_url_v1 falling back to NetEase (dolby) ids={}".format(missing_ids), xbmc.LOGDEBUG)
                    netease_data = self.request("POST", path, netease_params, custom_cookies={'os': 'pc', 'appver': '2.10.11.201538'})
                else:
                    netease_params = dict(ids=missing_ids if isinstance(ids, (list, tuple)) else json.dumps(missing_ids), level=level, encodeType='flac')
                    xbmc.log("plugin.audio.music: songs_url_v1 falling back to NetEase ids={}".format(missing_ids), xbmc.LOGDEBUG)
                    netease_data = self.request("POST", path, netease_params)

                xbmc.log("plugin.audio.music: songs_url_v1 netease response type={}".format(type(netease_data)), xbmc.LOGDEBUG)
                if isinstance(netease_data, dict) and 'data' in netease_data:
                    for item in netease_data.get('data') or []:
                        nid = item.get('id')
                        nurl = item.get('url')
                        for rd in result_data:
                            try:
                                if str(rd.get('id')) == str(nid) and (not rd.get('url')) and nurl:
                                    rd['url'] = nurl
                                    rd['source'] = 'netease'
                                    xbmc.log("plugin.audio.music: songs_url_v1 backfilled id={} url={}".format(nid, nurl), xbmc.LOGDEBUG)
                                    break
                            except Exception:
                                continue
            except Exception as e:
                xbmc.log("plugin.audio.music: songs_url_v1 netease fallback failed: {}".format(e), xbmc.LOGERROR)
                pass

        xbmc.log("plugin.audio.music: songs_url_v1 final result_data={}".format(result_data), xbmc.LOGDEBUG)
        return {'data': result_data}

    def tunehub_request(self, params):
        """Call TuneHub (music-dl.sayqz.com) API with given params and return parsed JSON or empty dict."""
        try:
            # 使用针对 TuneHub 的请求头：确保 Host 与 TUNEHUB_API 匹配（避免被远端拒绝）
            headers_for_tunehub = dict(self.header or {})
            try:
                host = urlparse(TUNEHUB_API).netloc
                if host:
                    headers_for_tunehub['Host'] = host
                    # 设置合适的 Referer 以减少被拒绝的可能
                    headers_for_tunehub['Referer'] = 'https://' + host + '/'
            except Exception:
                pass
            if not self.enable_proxy:
                resp = self.session.get(TUNEHUB_API, params=params, headers=headers_for_tunehub, timeout=DEFAULT_TIMEOUT)
            else:
                resp = self.session.get(TUNEHUB_API, params=params, headers=headers_for_tunehub, timeout=DEFAULT_TIMEOUT, proxies=self.proxies, verify=False)
            xbmc.log("plugin.audio.music: tunehub_request params={} status={} url={}".format(params, getattr(resp, 'status_code', 'N/A'), getattr(resp, 'url', 'N/A')), xbmc.LOGDEBUG)

            # 检查 HTTP 状态码，如果返回错误（如 502），则返回 None 表示 TuneHub API 失败
            status_code = getattr(resp, 'status_code', None)
            if status_code and status_code >= 400:
                xbmc.log("plugin.audio.music: tunehub_request HTTP error status={}, returning None for fallback".format(status_code), xbmc.LOGWARNING)
                return None

            # 尝试解析 JSON
            try:
                data = resp.json()
                xbmc.log("plugin.audio.music: tunehub_request response keys={}".format(list(data.keys()) if isinstance(data, dict) else type(data)), xbmc.LOGDEBUG)
                return data
            except Exception as e:
                xbmc.log("plugin.audio.music: tunehub_request json decode failed: {}".format(e), xbmc.LOGWARNING)
                # 非 JSON 响应：可能为重定向到音频文件或直接返回 URL 文本，尝试从 headers/url/text 中提取
                # 优先使用最终响应 URL（requests 会自动跟随重定向）
                try:
                    final_url = getattr(resp, 'url', None)
                    if final_url and final_url != TUNEHUB_API:
                        xbmc.log("plugin.audio.music: tunehub_request extracted url from resp.url={}".format(final_url), xbmc.LOGDEBUG)
                        return {'url': final_url}
                except Exception:
                    pass

                # 尝试从 Location header 中提取
                try:
                    loc = resp.headers.get('Location')
                    if loc:
                        xbmc.log("plugin.audio.music: tunehub_request extracted url from Location header={}".format(loc), xbmc.LOGDEBUG)
                        return {'url': loc}
                except Exception:
                    pass

                # 在响应文本中查找 URL
                try:
                    text = (resp.text or '')[:2048]
                    xbmc.log("plugin.audio.music: tunehub_request resp.text snippet={}".format(text[:200]), xbmc.LOGDEBUG)
                    m = re.search(r'(https?://[\w\-./?&=%#:~,+]+)', text)
                    if m:
                        found = m.group(1)
                        xbmc.log("plugin.audio.music: tunehub_request extracted url from body={}".format(found), xbmc.LOGDEBUG)
                        return {'url': found}
                except Exception as e2:
                    xbmc.log("plugin.audio.music: tunehub_request body parse failed: {}".format(e2), xbmc.LOGERROR)

                return {}
        except Exception as e:
            xbmc.log("plugin.audio.music: tunehub_request failed: {}".format(e), xbmc.LOGERROR)
            return None

    def tunehub_url(self, id, br=None, source='netease'):
        """Request TuneHub for a playable URL for `id`.

        Kept for backward compatibility; accepts optional `source` (platform).
        """
        params = {'source': source, 'id': id, 'type': 'url'}
        if br:
            params['br'] = str(br)
        return self.tunehub_request(params)

    def tunehub_api(self, source=None, id=None, type='info', br=None, keyword=None, limit=None, page=None):
        """Generic TuneHub API caller that supports the documented `type` values.

        Parameters mirror the public API: `source`, `id`, `type`, `br`, `keyword`, `limit`, `page`.
        Returns parsed JSON dict (or {}).
        """
        params = {}
        if type is not None:
            params['type'] = type
        if source is not None:
            params['source'] = source
        if id is not None:
            params['id'] = id
        if br is not None:
            params['br'] = str(br)
        if keyword is not None:
            params['keyword'] = keyword
        if limit is not None:
            params['limit'] = limit
        if page is not None:
            params['page'] = page

        return self.tunehub_request(params)

    def _normalize_tunehub_pics(self, resp):
        """Ensure TuneHub responses include a `pic` field for each item."""
        try:
            items = None
            # resp may be dict, list, or dict with nested data/list/lists
            if isinstance(resp, dict):
                # common places for lists
                if isinstance(resp.get('data'), list):
                    items = resp['data']
                elif isinstance(resp.get('data'), dict):
                    d = resp['data']
                    if isinstance(d.get('list'), list):
                        items = d['list']
                    elif isinstance(d.get('data'), list):
                        items = d['data']
                    elif isinstance(d.get('lists'), list):
                        items = d['lists']
                elif isinstance(resp.get('list'), list):
                    items = resp['list']
                elif isinstance(resp.get('lists'), list):
                    items = resp['lists']
            elif isinstance(resp, list):
                items = resp

            if items is None:
                return resp

            for it in items:
                if not isinstance(it, dict):
                    continue
                if not it.get('pic'):
                    it['pic'] = it.get('picUrl') or it.get('cover') or it.get('image') or it.get('thumbnail') or it.get('thumb') or ''
        except Exception:
            pass
        return resp

    # Convenience wrappers for common TuneHub types
    def tunehub_info(self, source, id):
        return self.tunehub_api(source=source, id=id, type='info')

    def tunehub_pic(self, source, id):
        return self.tunehub_api(source=source, id=id, type='pic')

    def tunehub_lrc(self, source, id):
        """Get lyrics from TuneHub API, handling direct LRC text response."""
        try:
            params = {'source': source, 'id': id, 'type': 'lrc'}
            headers_for_tunehub = dict(self.header or {})
            try:
                host = urlparse(TUNEHUB_API).netloc
                if host:
                    headers_for_tunehub['Host'] = host
                    headers_for_tunehub['Referer'] = 'https://' + host + '/'
            except Exception:
                pass
            if not self.enable_proxy:
                resp = self.session.get(TUNEHUB_API, params=params, headers=headers_for_tunehub, timeout=DEFAULT_TIMEOUT)
            else:
                resp = self.session.get(TUNEHUB_API, params=params, headers=headers_for_tunehub, timeout=DEFAULT_TIMEOUT, proxies=self.proxies, verify=False)

            xbmc.log("plugin.audio.music: tunehub_lrc params={} status={} url={}".format(params, getattr(resp, 'status_code', 'N/A'), getattr(resp, 'url', 'N/A')), xbmc.LOGDEBUG)

            # Try to parse as JSON first
            try:
                data = resp.json()
                xbmc.log("plugin.audio.music: tunehub_lrc response keys={}".format(list(data.keys()) if isinstance(data, dict) else type(data)), xbmc.LOGDEBUG)
                return data
            except ValueError:
                # Not JSON, treat as direct LRC text response
                text = resp.text.strip()
                xbmc.log("plugin.audio.music: tunehub_lrc treating as direct LRC text, length={}".format(len(text)), xbmc.LOGDEBUG)

                # Return in expected format - check if it looks like LRC content
                if text and ('[' in text or ']' in text):
                    # Return as dict with 'lrc' key to match expected format
                    return {'lrc': text, 'source': 'tunehub'}
                else:
                    # Empty or invalid response
                    return {}
        except Exception as e:
            xbmc.log("plugin.audio.music: tunehub_lrc failed: {}".format(e), xbmc.LOGERROR)
            return {}

    def tunehub_search(self, source, keyword, limit=20, page=1):
        resp = self.tunehub_api(source=source, type='search', keyword=keyword, limit=limit, page=page)
        return self._normalize_tunehub_pics(resp)

    def tunehub_aggregate_search(self, keyword, limit=20, page=1):
        resp = self.tunehub_api(type='aggregateSearch', keyword=keyword, limit=limit, page=page)
        return self._normalize_tunehub_pics(resp)

    def tunehub_playlist(self, source, id, limit=None, page=None):
        return self.tunehub_api(source=source, id=id, type='playlist', limit=limit, page=page)

    def tunehub_toplists(self, source=None, type='toplists'):
        # 请求 TuneHub 排行榜并对常见返回格式做兼容处理
        # 接受可选参数 `source` 和 `type`，保持向后兼容（addon.py 可不传参）
        resp = self.tunehub_api(source=source, type=type)
        try:
            if isinstance(resp, dict):
                data = resp.get('data')
                if isinstance(data, dict):
                    # 有些 TuneHub 接口返回 key 为 'list'，兼容为 'lists' 和 'data'
                    if 'list' in data:
                        if 'lists' not in data:
                            data['lists'] = data.get('list')
                        if 'data' not in data:
                            data['data'] = data.get('list')
        except Exception:
            pass
        return resp

    def tunehub_toplist(self, source, id, limit=None, page=None):
        return self.tunehub_api(source=source, id=id, type='toplist', limit=limit, page=page)

    # lyric http://music.163.com/api/song/lyric?os=osx&id= &lv=-1&kv=-1&tv=-1
    def song_lyric(self, music_id):
        path = "/weapi/song/lyric"
        params = dict(os="osx", id=music_id, lv=-1, kv=-1, tv=-1)
        return self.request("POST", path, params)

    # 今日最热（0）, 本周最热（10），历史最热（20），最新节目（30）
    def djchannels(self, offset=0, limit=50):
        path = "/weapi/djradio/hot/v1"
        params = dict(limit=limit, offset=offset)
        return self.request("POST", path, params)

    def dj_program(self, radio_id, asc=False, offset=0, limit=50):
        path = "/weapi/dj/program/byradio"
        params = dict(asc=asc, radioId=radio_id, offset=offset, limit=limit)
        return self.request("POST", path, params)

    def dj_sublist(self, offset=0, limit=50):
        path = "/weapi/djradio/get/subed"
        params = dict(offset=offset, limit=limit, total=True)
        return self.request("POST", path, params)

    def dj_detail(self, id):
        path = "/weapi/dj/program/detail"
        params = dict(id=id)
        return self.request("POST", path, params)

    # 打卡（上传播放记录）
    def daka(self, id, sourceId=0, time=240):
        """
        上传歌曲播放记录到网易云

        Args:
            id: 歌曲ID
            sourceId: 来源ID
            time: 播放时长（秒）
        """
        # 网易云播放记录上报 API
        # 使用 /weapi/feedback/weblog API
        path = "/weapi/feedback/weblog"
        
        # 根据网易云官方 API 文档，使用标准参数格式
        params = {'logs': json.dumps([{
            'action': 'play',
            'json': {
                "download": 0,
                "end": 'playend',
                "id": str(id),
                "sourceId": str(sourceId),
                "time": str(time),
                "type": 'song',
                "wifi": 0,
                "source": 'list'
            }
        }], ensure_ascii=False)}

        try:
            result = self.request("POST", path, params)
            print(f"[Daka] API 响应: song_id={id}")
            print(f"[Daka]   - code: {result.get('code')}")
            print(f"[Daka]   - msg: {result.get('msg')}")
            print(f"[Daka]   - data: {result.get('data')}")
            print(f"[Daka]   - 完整响应: {result}")
            
            # 检查响应状态
            if result.get('code') == 200:
                # 检查 data 字段，有些 API 返回 200 但 data 为空表示失败
                data = result.get('data', {})
                if data or result.get('msg') == 'success':
                    print(f"[Daka] 播放记录上传成功: song_id={id}, time={time}s, sourceId={sourceId}")
                    return result
                else:
                    print(f"[Daka] API 返回 200 但 data 为空，可能未成功")
                    
        except Exception as e:
            print(f"[Daka] 播放记录上传异常: song_id={id}, error={str(e)}")
            import traceback
            traceback.print_exc()

        # 返回失败结果
        return {"code": -1, "msg": "播放记录上传失败"}

    # 云盘歌曲
    def cloud_songlist(self, offset=0, limit=50):
        path = "/weapi/v1/cloud/get"
        params = dict(offset=offset, limit=limit, csrf_token="")
        return self.request("POST", path, params)

    # 歌手信息
    def artist_info(self, artist_id):
        path = "/weapi/v1/artist/{}".format(artist_id)
        return self.request("POST", path)

    def artist_songs(self, id, limit=50, offset=0):
        path = "/weapi/v1/artist/songs"
        params = dict(id=id, limit=limit, offset=offset,
                      private_cloud=True, work_type=1, order='hot')
        return self.request("POST", path, params)

    # 获取MV url
    def mv_url(self, id, r=1080):
        path = "/weapi/song/enhance/play/mv/url"
        params = dict(id=id, r=r)
        return self.request("POST", path, params)

    # 收藏的歌手
    def artist_sublist(self, offset=0, limit=50, total=True):
        path = "/weapi/artist/sublist"
        params = dict(offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    # 收藏的专辑
    def album_sublist(self, offset=0, limit=50, total=True):
        path = "/weapi/album/sublist"
        params = dict(offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    # 收藏的视频
    def video_sublist(self, offset=0, limit=50, total=True):
        path = "/weapi/cloudvideo/allvideo/sublist"
        params = dict(offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    # 获取视频url
    def video_url(self, id, resolution=1080):
        path = "/weapi/cloudvideo/playurl"
        params = dict(ids='["' + id + '"]', resolution=resolution)
        return self.request("POST", path, params)

   # 我的数字专辑
    def digitalAlbum_purchased(self, offset=0, limit=50, total=True):
        path = "/api/digitalAlbum/purchased"
        params = dict(offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    # 已购单曲
    def single_purchased(self, offset=0, limit=1000, total=True):
        path = "/weapi/single/mybought/song/list"
        params = dict(offset=offset, limit=limit)
        return self.request("POST", path, params)

    # 排行榜
    def toplists(self):
        path = "/api/toplist"
        return self.request("POST", path)

    # 新歌速递 全部:0 华语:7 欧美:96 日本:8 韩国:16
    def new_songs(self, areaId=0, total=True, use_cache=True):
        """
        获取新歌速递

        Args:
            areaId: 地区 ID (0:全部, 7:华语, 96:欧美, 8:日本, 16:韩国)
            total: 是否获取总数
            use_cache: 是否使用缓存 (默认 True)

        Returns:
            dict: 新歌数据
        """
        # 尝试从缓存读取
        if use_cache and CACHE_AVAILABLE:
            cache_db = get_cache_db()
            cache_key = cache_db.generate_cache_key('new_songs', areaId, total)
            cached_data = cache_db.get(cache_key)
            if cached_data is not None:
                xbmc.log('[plugin.audio.music] Using cached new_songs', xbmc.LOGDEBUG)
                return cached_data

        # 从 API 获取数据
        path = "/weapi/v1/discovery/new/songs"
        params = dict(areaId=areaId, total=total)
        result = self.request("POST", path, params)

        # 写入缓存
        if use_cache and CACHE_AVAILABLE and result:
            cache_db = get_cache_db()
            cache_db.set(cache_key, result, cache_type='new_songs')

        return result

    # 歌手MV
    def artist_mvs(self, id, offset=0, limit=50, total=True):
        path = "/weapi/artist/mvs"
        params = dict(artistId=id, offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    # 相似歌手
    def similar_artist(self, artistid):
        path = "/weapi/discovery/simiArtist"
        params = dict(artistid=artistid)
        return self.request("POST", path, params)

    # 用户信息
    def user_detail(self, id):
        path = "/weapi/v1/user/detail/{}".format(id)
        return self.request("POST", path)

    # 关注用户
    def user_follow(self, id):
        path = "/weapi/user/follow/{}".format(id)
        return self.request("POST", path)

    # 取消关注用户
    def user_delfollow(self, id):
        path = "/weapi/user/delfollow/{}".format(id)
        return self.request("POST", path)

    # 用户关注列表
    def user_getfollows(self, id, offset=0, limit=50, order=True):
        path = "/weapi/user/getfollows/{}".format(id)
        params = dict(offset=offset, limit=limit, order=order)
        return self.request("POST", path, params)

    # 用户粉丝列表
    def user_getfolloweds(self, userId, offset=0, limit=30):
        path = "/weapi/user/getfolloweds"
        params = dict(userId=userId, offset=offset,
                      limit=limit, getcounts=True)
        return self.request("POST", path, params)

    # 听歌排行 type: 0 全部时间 1最近一周
    def play_record(self, uid, type=0):
        path = "/weapi/v1/play/record"
        params = dict(uid=uid, type=type)
        return self.request("POST", path, params)

    # MV排行榜 area: 地区,可选值为内地,港台,欧美,日本,韩国,不填则为全部
    def top_mv(self, area='', limit=50, offset=0, total=True, use_cache=True):
        """
        获取热门 MV

        Args:
            area: 地区
            limit: 每页数量
            offset: 偏移量
            total: 是否获取总数
            use_cache: 是否使用缓存 (默认 True)

        Returns:
            dict: 热门 MV 数据
        """
        # 尝试从缓存读取
        if use_cache and CACHE_AVAILABLE:
            cache_db = get_cache_db()
            cache_key = cache_db.generate_cache_key('top_mv', area, limit, offset, total)
            cached_data = cache_db.get(cache_key)
            if cached_data is not None:
                xbmc.log('[plugin.audio.music] Using cached top_mv', xbmc.LOGDEBUG)
                return cached_data

        # 从 API 获取数据
        path = "/weapi/mv/toplist"
        params = dict(area=area, limit=limit, offset=offset, total=total)
        result = self.request("POST", path, params)

        # 写入缓存
        if use_cache and CACHE_AVAILABLE and result:
            cache_db = get_cache_db()
            cache_db.set(cache_key, result, cache_type='top_mv')

        return result

    def mlog_socialsquare(self, channelId=1001, pagenum=0):
        path = "/weapi/socialsquare/v1/get"
        params = dict(pagenum=pagenum, netstate=1, first=(
            str(pagenum) == '0'), channelId=channelId, dailyHot=(str(pagenum) == '0'))
        return self.request("POST", path, params)

    # 推荐MLOG
    def mlog_rcmd(self, id, limit=3, type=1, rcmdType=0, lastRcmdResType=1, lastRcmdResId='', viewCount=1, channelId=1001):
        path = "/weapi/mlog/rcmd/v3"
        params = dict(id=id, limit=limit, type=type, rcmdType=rcmdType,
                      lastRcmdResType=lastRcmdResType, extInfo=dict(channelId=channelId), viewCount=viewCount)
        return self.request("POST", path, params)

    # MLOG详情
    def mlog_detail(self, id, resolution=720, type=1):
        path = "/weapi/mlog/detail/v1"
        params = dict(id=id, resolution=resolution, type=type)
        return self.request("POST", path, params)

    # 创建歌单 privacy:0 为普通歌单，10 为隐私歌单；type:NORMAL|VIDEO
    def playlist_create(self, name, privacy=0, ptype='NORMAL'):
        path = "/weapi/playlist/create"
        params = dict(name=name, privacy=privacy, type=ptype)
        return self.request("POST", path, params)

    # 删除歌单
    def playlist_delete(self, ids):
        path = "/weapi/playlist/remove"
        params = dict(ids=ids)
        return self.request("POST", path, params)
        # {'code': 200}

    # 添加MV到视频歌单中
    def playlist_add(self, pid, ids):
        path = "/weapi/playlist/track/add"
        ids = [{'type': 3, 'id': song_id} for song_id in ids]
        params = {'id': pid, 'tracks': json.dumps(ids)}
        return self.request("POST", path, params)

    # 添加/删除单曲到歌单
    # op:'add'|'del'
    def playlist_tracks(self, pid, ids, op='add'):
        path = "/weapi/playlist/manipulate/tracks"
        params = {'op': op, 'pid': pid,
                  'trackIds': json.dumps(ids), 'imme': 'true'}
        result = self.request("POST", path, params)
        # 可以收藏收费歌曲和下架歌曲
        if result['code'] != 200:
            ids.extend(ids)
            params = {'op': op, 'pid': pid,
                      'trackIds': json.dumps(ids), 'imme': 'true'}
            result = self.request("POST", path, params)
        return result

    # 收藏歌单
    def playlist_subscribe(self, id):
        path = "/weapi/playlist/subscribe"
        params = dict(id=id)
        return self.request("POST", path, params)

    # 取消收藏歌单
    def playlist_unsubscribe(self, id):
        path = "/weapi/playlist/unsubscribe"
        params = dict(id=id)
        return self.request("POST", path, params)

    def user_level(self):
        path = "/weapi/user/level"
        return self.request("POST", path)

    # ========== 短信验证码登录支持 ==========

    def login_send_captcha(self, phone):
        """发送短信验证码"""
        # 使用移动端 API 接口
        path = '/weapi/sms/captcha/sent'
        params = dict(
            phone=phone,
            ctcode='86'  # 中国区号
        )

        # 设置移动端 Cookie 模拟
        custom_cookies = {
            'os': 'android',
            'appver': '9.2.70',
            'deviceId': self._generate_device_id()
        }

        # 使用移动端请求头
        return self.request("POST", path, params, custom_cookies=custom_cookies, use_mobile_header=True)

    def login_verify_captcha(self, phone, captcha):
        """验证短信验证码并登录"""
        # 使用移动端 API 接口
        path = '/weapi/sms/captcha/verify'
        params = dict(
            phone=phone,
            captcha=captcha,
            ctcode='86'
        )

        # 设置移动端 Cookie 模拟
        custom_cookies = {
            'os': 'android',
            'appver': '9.2.70',
            'deviceId': self._generate_device_id()
        }

        # 使用移动端请求头
        data = self.request("POST", path, params, custom_cookies=custom_cookies, use_mobile_header=True)

        # 如果验证成功，保存 cookie
        if data.get('code', 0) == 200:
            self.session.cookies.save()

        return data

    def login_qr_key(self):
        """获取二维码登录的 key"""
        # 使用移动端 API 接口
        path = '/weapi/login/qrcode/unikey'
        params = dict(type=1)

        # 设置移动端 Cookie 模拟
        custom_cookies = {
            'os': 'android',
            'appver': '9.2.70',
            'deviceId': self._generate_device_id()
        }

        # 使用移动端请求头
        return self.request("POST", path, params, custom_cookies=custom_cookies, use_mobile_header=True)

    def login_qr_check(self, key):
        """检查二维码登录状态"""
        path = '/weapi/login/qrcode/client/login'
        params = dict(key=key, type=1)

        # 设置移动端 Cookie 模拟
        custom_cookies = {
            'os': 'android',
            'appver': '9.2.70',
            'deviceId': self._generate_device_id()
        }

        # 使用移动端请求头
        data = self.request("POST", path, params, custom_cookies=custom_cookies, use_mobile_header=True)
        if data.get('code', 0) == 803:
            self.session.cookies.save()
        return data

    def _generate_device_id(self):
        """生成设备 ID（用于模拟移动端）"""
        import hashlib
        import random
        import time

        # 生成一个固定的设备 ID（基于时间戳和随机数）
        # 使用 MD5 生成 32 位设备 ID
        raw = f"{int(time.time() * 1000)}-{random.randint(100000, 999999)}"
        device_id = hashlib.md5(raw.encode('utf-8')).hexdigest()

        # 网易云音乐设备 ID 格式：16 位十六进制
        return device_id[:32]

    def vip_timemachine(self, startTime, endTime, limit=60):
        path = '/weapi/vipmusic/newrecord/weekflow'
        params = dict(startTime=startTime,
                      endTime=endTime, type=1, limit=limit)
        return self.request("POST", path, params)

    # ========== LXMUSIC API 集成 ==========

    @staticmethod
    def _lxmusic_sha256(message: str) -> str:
        """
        SHA256 哈希函数（用于 LXMUSIC API）

        Args:
            message: 待哈希的字符串

        Returns:
            SHA256 哈希值的十六进制字符串
        """
        return hashlib.sha256(message.encode('utf-8')).hexdigest()

    # ========== GD Music API 集成 ==========

    def _gdmusic_request(self, types, **params):
        """
        向 GD Music API 发送请求

        Args:
            types: API 类型 (search, url, pic, lyric)
            **params: API 参数

        Returns:
            dict: API 响应数据，失败返回 None
        """
        params['types'] = types
        url = GD_MUSIC_API_URL + '?' + urlencode(params)

        xbmc.log("plugin.audio.music: GD Music API 请求: %s" % url[:150], xbmc.LOGDEBUG)

        # 浏览器风格的请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'DNT': '1',
            'Connection': 'keep-alive',
        }

        # 重试机制：最多 3 次尝试
        for attempt in range(3):
            try:
                if attempt > 0:
                    wait_time = min(2 ** attempt, 10)  # 最多等待 10 秒
                    xbmc.log("plugin.audio.music: GD Music API 重试 %d/%d，等待 %d 秒" % (attempt + 1, 3, wait_time), xbmc.LOGINFO)
                    time.sleep(wait_time)

                https_url = url.replace('http://', 'https://')

                # 尝试不同的 SSL 策略
                if attempt == 0:
                    # 第一次尝试：使用 HTTPS
                    response = requests.get(https_url, headers=headers, timeout=20)
                elif attempt == 1:
                    # 第二次尝试：跳过 SSL 验证
                    response = requests.get(https_url, headers=headers, timeout=20, verify=False)
                else:
                    # 最后尝试：使用 HTTP
                    http_url = url.replace('https://', 'http://')
                    response = requests.get(http_url, headers=headers, timeout=20)

                response.raise_for_status()

                xbmc.log("plugin.audio.music: GD Music API 响应状态: %d" % response.status_code, xbmc.LOGDEBUG)

                # 检查响应是否为空
                if not response.content:
                    xbmc.log("plugin.audio.music: GD Music API 返回空响应", xbmc.LOGERROR)
                    continue

                # 尝试解析 JSON
                try:
                    data = response.json()
                    xbmc.log("plugin.audio.music: GD Music API 尝试 %d 成功" % (attempt + 1), xbmc.LOGDEBUG)
                    return data
                except ValueError as json_error:
                    xbmc.log("plugin.audio.music: GD Music API JSON 解析失败: %s" % str(json_error), xbmc.LOGERROR)
                    xbmc.log("plugin.audio.music: GD Music API 响应文本: %s" % response.text[:500], xbmc.LOGERROR)
                    continue

            except requests.exceptions.RequestException as e:
                xbmc.log("plugin.audio.music: GD Music API 尝试 %d/%d 失败: %s" % (attempt + 1, 3, str(e)), xbmc.LOGERROR)
                if attempt == 2:  # 最后一次尝试
                    xbmc.log("plugin.audio.music: GD Music API 所有重试均失败", xbmc.LOGERROR)
                    return None
                continue

        return None

    def _gdmusic_get_play_url_with_fallback(self, track_id, quality='320', song_name='', artist_name='', original_source='netease'):
        """
        使用 GD Music API 获取播放 URL，支持多音乐源优先级回退

        优先级顺序：原音乐源 > kuwo > joox > netease

        重要：换源时，歌曲ID是源特定的，不能直接复用。
        需要使用歌曲信息（歌名、歌手）在新源重新搜索，获取新源的歌曲ID。

        Args:
            track_id: 歌曲 ID（原源的ID）
            quality: 音质（默认 320）
            song_name: 歌曲名称（用于换源时重新搜索）
            artist_name: 歌手名称（用于换源时重新搜索）
            original_source: 原始音乐源（用于判断是否需要重新搜索）

        Returns:
            tuple: (play_url, source) 或 (None, None) 如果所有源都失败
        """
        # 构建优先级列表：原音乐源 > kuwo > joox > netease
        # 排除重复的音乐源
        fallback_sources = ['kuwo', 'joox', 'netease']
        source_priority = [original_source] + [s for s in fallback_sources if s != original_source]

        xbmc.log("plugin.audio.music: GD Music 回退: track_id=%s, quality=%s, song=%s, artist=%s, original_source=%s" %
                 (track_id, quality, song_name, artist_name, original_source), xbmc.LOGDEBUG)
        xbmc.log("plugin.audio.music: GD Music 优先级: %s" % ' > '.join(source_priority), xbmc.LOGDEBUG)

        # 按优先级尝试每个音乐源
        for source in source_priority:
            xbmc.log("plugin.audio.music: GD Music 尝试音源: %s" % source, xbmc.LOGDEBUG)

            # 判断是否需要重新搜索
            # 如果当前尝试的源与原始源不同，说明在换源，需要重新搜索
            need_search = (source != original_source)

            if need_search:
                # 换源时，需要使用歌曲信息在新源重新搜索
                if not song_name:
                    xbmc.log("plugin.audio.music: GD Music 换源失败：song_name 为空", xbmc.LOGWARNING)
                    continue

                xbmc.log("plugin.audio.music: GD Music 换源，在新源搜索: %s - %s" % (source, song_name, artist_name), xbmc.LOGDEBUG)

                # 在新源搜索歌曲
                # 优先只用歌名搜索，如果失败再用"歌手+歌名"
                search_query = song_name
                search_data = self._gdmusic_request('search', source=source, name=search_query, count='1', pages='1')

                # 如果只用歌名搜索没有结果，尝试用"歌手+歌名"
                if not search_data or not isinstance(search_data, list) or len(search_data) == 0:
                    if artist_name:
                        xbmc.log("plugin.audio.music: GD Music 歌名搜索失败，尝试用歌手+歌名: %s %s" % (artist_name, song_name), xbmc.LOGDEBUG)
                        search_query = '%s %s' % (artist_name, song_name)
                        search_data = self._gdmusic_request('search', source=source, name=search_query, count='1', pages='1')

                if not search_data or not isinstance(search_data, list) or len(search_data) == 0:
                    xbmc.log("plugin.audio.music: GD Music 在 %s 中搜索失败或无结果" % source, xbmc.LOGWARNING)
                    continue

                # 获取搜索结果中的第一首歌曲
                new_track = search_data[0]
                new_track_id = new_track.get('id', '')

                if not new_track_id:
                    xbmc.log("plugin.audio.music: GD Music 在 %s 的搜索结果中未找到有效的 track_id" % source, xbmc.LOGWARNING)
                    continue

                xbmc.log("plugin.audio.music: GD Music 在 %s 中找到歌曲: id=%s, name=%s" % (source, new_track_id, new_track.get('name', '')), xbmc.LOGDEBUG)

                # 使用新源的ID获取播放URL
                data = self._gdmusic_request('url', source=source, id=new_track_id, br=quality)
            else:
                # 同源，直接使用原ID
                data = self._gdmusic_request('url', source=source, id=track_id, br=quality)

            if data and 'url' in data and data['url']:
                play_url = data['url']
                xbmc.log("plugin.audio.music: GD Music 成功从 %s 获取播放链接: %s" % (source, play_url[:80] + '...'), xbmc.LOGINFO)
                return play_url, source

            xbmc.log("plugin.audio.music: GD Music 从 %s 获取播放链接失败" % source, xbmc.LOGWARNING)

        # 所有音乐源都失败
        xbmc.log("plugin.audio.music: GD Music 所有音源均失败: track_id=%s" % track_id, xbmc.LOGERROR)
        return None, None

    @staticmethod
    def _lxmusic_generate_sign(request_path: str) -> str:
        """
        生成 LXMUSIC API 请求签名

        签名算法: SHA256(requestPath + SCRIPT_MD5 + SECRET_KEY)

        Args:
            request_path: 请求路径

        Returns:
            签名字符串
        """
        return NetEase._lxmusic_sha256(request_path + LXMUSIC_SCRIPT_MD5 + LXMUSIC_SECRET_KEY)

    @staticmethod
    def _lxmusic_make_request(url: str, timeout: int = 10) -> dict:
        """
        发送 LXMUSIC API HTTP 请求

        Args:
            url: 完整的请求 URL
            timeout: 超时时间（秒）

        Returns:
            响应 JSON 数据

        Raises:
            Exception: 请求失败或响应解析失败
        """
        headers = {
            'accept': 'application/json',
            'x-request-key': LXMUSIC_API_KEY,
            'user-agent': 'lx-music-mobile/2.0.0'
        }

        try:
            response = requests.get(url, headers=headers, timeout=timeout)

            # 检查 HTTP 状态码
            if response.status_code == 404:
                raise Exception('LXMUSIC API端点不存在')
            elif response.status_code >= 500:
                raise Exception(f'LXMUSIC 服务器错误 ({response.status_code})')

            # 解析 JSON 响应
            try:
                data = response.json()
            except json.JSONDecodeError:
                raise Exception('LXMUSIC 响应解析失败: 无效的 JSON 格式')

            return data

        except requests.exceptions.Timeout:
            raise Exception('LXMUSIC 请求超时')
        except requests.exceptions.ConnectionError:
            raise Exception('LXMUSIC 连接失败，请检查网络')
        except requests.exceptions.RequestException as e:
            raise Exception(f'LXMUSIC 请求失败: {str(e)}')

    @staticmethod
    def _lxmusic_get_music_url_single(source: str, songmid: str, quality: str, timeout: int = 10) -> str:
        """
        单次尝试从 LXMUSIC API 获取音乐播放链接

        Args:
            source: LXMUSIC 音源标识符 (wy/tx/mg/kg/kw/jm/dp/xm/ap/sp/yt/qd/td)
            songmid: 歌曲ID
            quality: 音质 (128k/320k/flac/flac24bit/hires/atmos/atmos_plus/master)
            timeout: 超时时间（秒）

        Returns:
            播放链接字符串，失败返回空字符串

        Raises:
            Exception: 获取失败
        """
        # 构建请求路径
        request_path = f'/lxmusicv4/url/{source}/{songmid}/{quality}'
        sign = NetEase._lxmusic_generate_sign(request_path)
        url = f'{LXMUSIC_API_URL}{request_path}?sign={sign}'

        xbmc.log(f"plugin.audio.music: LXMUSIC 请求 URL: {url}", xbmc.LOGDEBUG)

        # 发送请求
        data = NetEase._lxmusic_make_request(url, timeout)

        xbmc.log(f"plugin.audio.music: LXMUSIC 响应数据: {data}", xbmc.LOGDEBUG)

        # 检查响应数据
        if not data or 'code' not in data:
            raise Exception('LXMUSIC 无效的响应数据')

        code = data.get('code')

        # 检查业务状态码
        if code in [0, 200]:
            music_url = data.get('data') or data.get('url')
            if music_url:
                xbmc.log(f"plugin.audio.music: LXMUSIC 获取播放链接成功: {music_url}", xbmc.LOGDEBUG)
                return music_url
            else:
                raise Exception('LXMUSIC 响应中未找到有效的URL')
        elif code == 403:
            raise Exception('LXMUSIC Key失效/鉴权失败')
        elif code == 429:
            raise Exception('LXMUSIC 请求过速，请稍后再试')
        else:
            error_msg = data.get('msg') or data.get('message') or '未知错误'
            raise Exception(f'LXMUSIC 错误: {error_msg}')

    def _lxmusic_get_music_url(self, source: str, songmid: str, quality: str,
                              max_retries: int = 3, timeout: int = 10) -> str:
        """
        从 LXMUSIC API 获取音乐播放链接（带重试机制）

        Args:
            source: LXMUSIC 音源标识符
            songmid: 歌曲ID
            quality: 音质
            max_retries: 最大重试次数
            timeout: 超时时间（秒）

        Returns:
            播放链接字符串，失败返回空字符串
        """
        if not songmid:
            xbmc.log("plugin.audio.music: LXMUSIC songmid 不能为空", xbmc.LOGWARNING)
            return ''

        # 带重试机制的请求
        last_error = None
        for attempt in range(max_retries):
            try:
                xbmc.log(f"plugin.audio.music: LXMUSIC 尝试 {attempt + 1}/{max_retries} 获取播放链接", xbmc.LOGDEBUG)
                url = self._lxmusic_get_music_url_single(source, songmid, quality, timeout)
                if url:
                    return url
            except Exception as e:
                last_error = e
                xbmc.log(f"plugin.audio.music: LXMUSIC 尝试 {attempt + 1} 失败: {str(e)}", xbmc.LOGWARNING)

                # 如果是 429 错误（请求过速），使用指数退避
                if '429' in str(e) and attempt < max_retries - 1:
                    backoff_time = min(2 ** attempt, 10)  # 最多等待 10 秒
                    time.sleep(backoff_time)
                    continue

                # 其他错误直接抛出
                if attempt < max_retries - 1:
                    time.sleep(1)  # 短暂等待后重试
                else:
                    raise

        # 所有重试都失败
        if last_error:
            xbmc.log(f"plugin.audio.music: LXMUSIC 所有重试失败: {str(last_error)}", xbmc.LOGERROR)

        return ''

    def _convert_level_to_quality(self, level: str) -> str:
        """
        将网易云的 level 转换为 LXMUSIC 的 quality

        Args:
            level: 网易云音质级别 (standard/exceed/high/lossless/hires/dolby/jyeffect/jymaster)

        Returns:
            LXMUSIC 音质标识符 (128k/320k/flac/flac24bit/hires/atmos/atmos_plus/master)
        """
        level_mapping = {
            'standard': '128k',
            'exceed': '320k',
            'high': '320k',
            'lossless': 'flac',
            'hires': 'flac24bit',
            'dolby': 'atmos',
            'jyeffect': 'flac',
            'jymaster': 'master'
        }
        return level_mapping.get(level, '320k')

    def _convert_level_to_gdmusic_quality(self, level: str) -> str:
        """
        将网易云的 level 转换为 GD Music API 的 quality

        Args:
            level: 网易云音质级别 (standard/exceed/high/lossless/hires/dolby/jyeffect/jymaster)

        Returns:
            GD Music API 音质标识符 (128/192/320/740/999)
        """
        level_mapping = {
            'standard': '128',
            'exceed': '320',
            'high': '320',
            'lossless': '740',
            'hires': '999',
            'dolby': '999',
            'jyeffect': '740',
            'jymaster': '999'
        }
        return level_mapping.get(level, '320')

    def _convert_quality_to_gdmusic_quality(self, quality: str) -> str:
        """
        将 LXMUSIC 的 quality 转换为 GD Music API 的 quality

        Args:
            quality: LXMUSIC 音质标识符 (128k/320k/flac/flac24bit/hires/atmos/atmos_plus/master)

        Returns:
            GD Music API 音质标识符 (128/192/320/740/999)
        """
        quality_mapping = {
            '128k': '128',
            '320k': '320',
            'flac': '740',
            'flac24bit': '999',
            'hires': '999',
            'atmos': '999',
            'atmos_plus': '999',
            'master': '999'
        }
        return quality_mapping.get(quality, '320')

    def _search_music_by_name(self, keyword: str, source: str = 'kuwo', limit: int = 5) -> list:
        """
        通过搜索 API 搜索音乐

        Args:
            keyword: 搜索关键词（歌曲名或歌手名）
            source: 音源 (kuwo/netease/tencent/migu/kugou)
            limit: 返回结果数量

        Returns:
            搜索结果列表，每个元素包含歌曲信息
        """
        if not keyword:
            return []

        params = {
            'types': 'search',
            'source': source,
            'name': keyword,
            'count': limit,
            'pages': 1
        }

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            xbmc.log(f"plugin.audio.music: 搜索API请求: keyword={keyword}, source={source}", xbmc.LOGDEBUG)
            response = requests.get(SEARCH_API_URL, params=params, headers=headers, timeout=10)

            if response.status_code != 200:
                xbmc.log(f"plugin.audio.music: 搜索API请求失败，状态码: {response.status_code}", xbmc.LOGWARNING)
                return []

            data = response.json()
            xbmc.log(f"plugin.audio.music: 搜索API响应: {data}", xbmc.LOGDEBUG)

            # 处理响应数据
            songs = data if isinstance(data, list) else data.get('data', [])

            # 转换为统一格式
            result = []
            for song in songs:
                result.append({
                    'id': song.get('id') or song.get('track_id') or '',
                    'name': song.get('name') or song.get('title') or '',
                    'artist': song.get('artist') or song.get('singer') or '',
                    'album': song.get('album') or song.get('album_name') or '',
                    'source': song.get('source') or source
                })

            xbmc.log(f"plugin.audio.music: 搜索API找到 {len(result)} 首歌曲", xbmc.LOGDEBUG)
            return result

        except Exception as e:
            xbmc.log(f"plugin.audio.music: 搜索API异常: {str(e)}", xbmc.LOGERROR)
            return []

    def _check_url_valid(self, url: str) -> bool:
        """
        检查 URL 是否可用（通过 HEAD 请求）

        Args:
            url: 要检查的 URL

        Returns:
            URL 是否可用
        """
        if not url:
            return False

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
            xbmc.log(f"plugin.audio.music: URL检查 {url[:50]}... 状态码: {response.status_code}", xbmc.LOGDEBUG)
            return response.status_code == 200
        except Exception as e:
            xbmc.log(f"plugin.audio.music: URL检查失败: {str(e)}", xbmc.LOGWARNING)
            return False

    def _get_song_info_from_netease(self, song_id: str) -> dict:
        """
        从网易云获取歌曲信息（用于搜索回退）

        Args:
            song_id: 歌曲ID

        Returns:
            歌曲信息字典 {'name': song_name, 'artist': artist_name}
        """
        try:
            xbmc.log(f"plugin.audio.music: 从网易云获取歌曲信息 id={song_id}", xbmc.LOGDEBUG)
            data = self.songs_detail([song_id])

            if data and 'songs' in data and len(data['songs']) > 0:
                song = data['songs'][0]
                song_name = song.get('name', '')
                artist_list = song.get('ar', [])
                artist_name = ', '.join([ar.get('name', '') for ar in artist_list]) if artist_list else ''

                xbmc.log(f"plugin.audio.music: 从网易云获取歌曲信息成功: name={song_name}, artist={artist_name}", xbmc.LOGDEBUG)
                return {'name': song_name, 'artist': artist_name}
            else:
                xbmc.log(f"plugin.audio.music: 从网易云获取歌曲信息失败: 未找到歌曲", xbmc.LOGWARNING)
                return {}
        except Exception as e:
            xbmc.log(f"plugin.audio.music: 从网易云获取歌曲信息异常: {str(e)}", xbmc.LOGERROR)
            return {}

    def _search_and_retry_lxmusic(self, song_id: str, song_name: str, artist_name: str,
                                  target_source: str, quality: str) -> str:
        """
        通过搜索 API 获取新的歌曲 ID，然后重新调用 LXMUSIC API

        按照顺序尝试不同的音源: kuwo, tencent, migu, kugou, netease

        Args:
            song_id: 原始歌曲 ID
            song_name: 歌曲名称
            artist_name: 歌手名称
            target_source: 目标音源 (LXMUSIC 标识符，如 wy/tx/mg/kg/kw)
            quality: 音质

        Returns:
            播放链接，失败返回空字符串
        """
        # 定义搜索回退的音源顺序（优先使用其他音源）
        search_sources_order = ['kuwo', 'tencent', 'migu', 'kugou', 'netease']

        # 音源映射（搜索 API 音源 → LXMUSIC 音源标识符）
        source_mapping = {
            'kuwo': 'kw',
            'tencent': 'tx',
            'migu': 'mg',
            'kugou': 'kg',
            'netease': 'wy'
        }

        xbmc.log(f"plugin.audio.music: 开始搜索回退: song_id={song_id}, song_name={song_name}, artist={artist_name}, 原始源={target_source}", xbmc.LOGDEBUG)

        # 如果没有提供歌曲名称或歌手名称，尝试从网易云获取
        if not song_name and not artist_name:
            xbmc.log(f"plugin.audio.music: 未提供歌曲信息，尝试从网易云获取", xbmc.LOGDEBUG)
            song_info = self._get_song_info_from_netease(song_id)
            if song_info:
                song_name = song_info.get('name', '')
                artist_name = song_info.get('artist', '')
                xbmc.log(f"plugin.audio.music: 从网易云获取到歌曲信息: name={song_name}, artist={artist_name}", xbmc.LOGDEBUG)

        # 如果仍然没有歌曲信息，无法进行搜索回退
        if not song_name and not artist_name:
            xbmc.log(f"plugin.audio.music: 无法获取歌曲信息，跳过搜索回退", xbmc.LOGWARNING)
            return ''

        # 构建搜索关键词
        if song_name and artist_name:
            keyword = f"{song_name} {artist_name}"
        elif song_name:
            keyword = song_name
        else:
            keyword = str(song_id)

        xbmc.log(f"plugin.audio.music: 搜索关键词: {keyword}", xbmc.LOGDEBUG)

        # 按照顺序尝试每个音源
        for search_source in search_sources_order:
            lxmusic_source = source_mapping.get(search_source)
            if not lxmusic_source:
                xbmc.log(f"plugin.audio.music: 跳过不支持的音源: {search_source}", xbmc.LOGDEBUG)
                continue

            xbmc.log(f"plugin.audio.music: 尝试音源: {search_source} -> {lxmusic_source}", xbmc.LOGDEBUG)

            try:
                # 在当前音源中搜索歌曲
                search_results = self._search_music_by_name(keyword, search_source, limit=3)

                if not search_results:
                    xbmc.log(f"plugin.audio.music: 音源 {search_source} 未找到搜索结果", xbmc.LOGDEBUG)
                    continue

                xbmc.log(f"plugin.audio.music: 音源 {search_source} 找到 {len(search_results)} 首歌曲", xbmc.LOGDEBUG)

                # 尝试每个搜索结果
                for song in search_results:
                    new_song_id = song.get('id')
                    if not new_song_id:
                        continue

                    xbmc.log(f"plugin.audio.music: 尝试搜索结果: id={new_song_id}, name={song.get('name')}, artist={song.get('artist')}", xbmc.LOGDEBUG)

                    new_url = None
                    lxmusic_error = None

                    # 使用新的歌曲 ID 调用 LXMUSIC API
                    try:
                        new_url = self._lxmusic_get_music_url(lxmusic_source, new_song_id, quality)
                    except Exception as e:
                        lxmusic_error = str(e)
                        xbmc.log(f"plugin.audio.music: LXMUSIC API 异常: {str(e)}", xbmc.LOGWARNING)

                    # 检查 LXMUSIC API 结果
                    if new_url:
                        # 检查 URL 是否可用
                        if self._check_url_valid(new_url):
                            xbmc.log(f"plugin.audio.music: 搜索回退成功: 原ID={song_id} -> 新ID={new_song_id}, 音源={search_source}, URL={new_url}", xbmc.LOGINFO)
                            return new_url
                        else:
                            xbmc.log(f"plugin.audio.music: 搜索回退URL不可用: {new_url}", xbmc.LOGWARNING)
                            new_url = None  # 标记为失败，触发 GD Music API

                    # 如果 LXMUSIC API 失败或返回空结果，尝试使用 GD Music API
                    if not new_url:
                        xbmc.log(f"plugin.audio.music: LXMUSIC API 失败，尝试使用 GD Music API: id={new_song_id}, source={search_source}, error={lxmusic_error}", xbmc.LOGDEBUG)
                        try:
                            # 将 LXMUSIC quality 转换为 GD Music quality
                            gd_quality = self._convert_quality_to_gdmusic_quality(quality)
                            gdmusic_url, gdmusic_source = self._gdmusic_get_play_url_with_fallback(
                                new_song_id, quality=gd_quality,
                                song_name=song.get('name'),
                                artist_name=song.get('artist'),
                                original_source=search_source
                            )
                            if gdmusic_url and self._check_url_valid(gdmusic_url):
                                xbmc.log(f"plugin.audio.music: GD Music API 搜索回退成功: 原ID={song_id} -> 新ID={new_song_id}, 音源={gdmusic_source}, URL={gdmusic_url}", xbmc.LOGINFO)
                                return gdmusic_url
                            else:
                                xbmc.log(f"plugin.audio.music: GD Music API 搜索回退失败: id={new_song_id}, source={search_source}", xbmc.LOGWARNING)
                        except Exception as ge:
                            xbmc.log(f"plugin.audio.music: GD Music API 搜索回退异常: {str(ge)}", xbmc.LOGWARNING)
                        continue  # 继续尝试下一个搜索结果

                # 如果当前音源的所有搜索结果都失败，尝试下一个音源
                xbmc.log(f"plugin.audio.music: 音源 {search_source} 所有搜索结果均失败，尝试下一个音源", xbmc.LOGDEBUG)

            except Exception as e:
                xbmc.log(f"plugin.audio.music: 音源 {search_source} 搜索异常: {str(e)}", xbmc.LOGERROR)
                continue

        xbmc.log(f"plugin.audio.music: 搜索回退所有音源均失败", xbmc.LOGWARNING)
        return ''
