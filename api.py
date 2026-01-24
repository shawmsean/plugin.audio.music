# -*- coding:utf-8 -*-
import json
import os
import sys
import time
import requests
import re
from urllib.parse import urlparse
from encrypt import encrypted_request
from xbmcswift2 import xbmc, xbmcaddon, xbmcplugin # type: ignore
from http.cookiejar import Cookie
from http.cookiejar import MozillaCookieJar
import xbmcvfs # pyright: ignore[reportMissingImports]
try:
    xbmc.translatePath = xbmcvfs.translatePath
except AttributeError:
    pass

DEFAULT_TIMEOUT = 10

BASE_URL = "https://music.163.com"
TUNEHUB_API = "https://music-dl.sayqz.com/api/"

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
    def recommend_resource(self):
        path = "/weapi/v1/discovery/recommend/resource"
        return self.request("POST", path)

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
    def new_albums(self, offset=0, limit=50):
        path = "/weapi/album/new"
        params = dict(area="ALL", offset=offset, total=True, limit=limit)
        return self.request("POST", path, params)

    # 歌单（网友精选碟） hot||new http://music.163.com/#/discover/playlist/
    def top_playlists(self, category="全部", order="hot", offset=0, limit=50):
        path = "/weapi/playlist/list"
        params = dict(
            cat=category, order=order, offset=offset, total="true", limit=limit
        )
        return self.request("POST", path, params)
    
        # 歌单（网友精选碟） hot||new http://music.163.com/#/discover/playlist/
    def hot_playlists(self, category="全部", order="hot", offset=0, limit=50):
        path = "/weapi/playlist/list"
        params = dict(
            cat=category, order=order, offset=offset, total="true", limit=limit
        )
        return self.request("POST", path, params)

    def playlist_catelogs(self):
        path = "/weapi/playlist/catalogue"
        return self.request("POST", path)

    # 歌单详情
    def playlist_detail(self, id, shareUserId=0):
        path = "/weapi/v6/playlist/detail"
        params = dict(id=id, t=int(time.time()), n=1000,
                      s=5, shareUserId=shareUserId)

        return (self.request("POST", path, params))

    # 热门歌手 http://music.163.com/#/discover/artist/
    def top_artists(self, offset=0, limit=100, total=True):
        path = "/weapi/artist/top"
        params = dict(offset=offset, total=total, limit=limit)
        return self.request("POST", path, params)

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

    def songs_url_v1(self, ids, level, source='netease'):
        path = "/weapi/song/enhance/player/url/v1"

        # 先使用 TuneHub 逐条获取播放地址，缺失的再回退到网易云原接口
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

        xbmc.log("plugin.audio.music: songs_url_v1 ids_list={}".format(ids_list), xbmc.LOGDEBUG)
        result_data = []
        missing_ids = []
        for _id in ids_list:
            url = None
            try:
                xbmc.log("plugin.audio.music: songs_url_v1 trying TuneHub id={}".format(_id), xbmc.LOGDEBUG)
                tun = self.tunehub_url(_id, source=source)
                xbmc.log("plugin.audio.music: songs_url_v1 tunehub raw for id={} -> {}".format(_id, tun), xbmc.LOGDEBUG)
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
            except Exception:
                url = None

            xbmc.log("plugin.audio.music: songs_url_v1 tunehub resolved id={} url={}".format(_id, url), xbmc.LOGDEBUG)
            result_data.append({'id': _id, 'url': url, 'level': level})
            if not url:
                missing_ids.append(_id)

        # 回退网易原始接口以获取剩余的播放地址
        if missing_ids:
            xbmc.log("plugin.audio.music: songs_url_v1 missing_ids after TuneHub: {}".format(missing_ids), xbmc.LOGDEBUG)
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
                                    xbmc.log("plugin.audio.music: songs_url_v1 backfilled id={} url={}".format(nid, nurl), xbmc.LOGDEBUG)
                                    break
                            except Exception:
                                continue
            except Exception as e:
                xbmc.log("plugin.audio.music: songs_url_v1 netease fallback failed: {}".format(e), xbmc.LOGERROR)
                pass

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
            return {}

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
    def new_songs(self, areaId=0, total=True):
        path = "/weapi/v1/discovery/new/songs"
        params = dict(areaId=areaId, total=total)
        return self.request("POST", path, params)

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
    def top_mv(self, area='', limit=50, offset=0, total=True):
        path = "/weapi/mv/toplist"
        params = dict(area=area, limit=limit, offset=offset, total=total)
        return self.request("POST", path, params)

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
