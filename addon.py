# -*- coding:utf-8 -*-
from api import NetEase
from xbmcswift2 import Plugin, xbmcgui, xbmcplugin, xbmc, xbmcaddon # type: ignore
import sqlite3
import re
import sys
import hashlib
import time
import os
import xbmcvfs # type: ignore
import qrcode # type: ignore
from datetime import datetime
import json
try:
    xbmc.translatePath = xbmcvfs.translatePath
except AttributeError:
    pass

PY3 = sys.version_info.major >= 3
if not PY3:
    reload(sys) # type: ignore
    sys.setdefaultencoding('utf-8')

plugin = Plugin()
def safe_get_storage(name, **kwargs):
    """Attempt to get persistent storage, fall back to an in-memory dict on error.

    This prevents PermissionError or other IO errors from crashing the addon.
    """
    try:
        return plugin.get_storage(name, **kwargs)
    except Exception as e:
        try:
            xbmc.log('plugin.audio.music163: get_storage(%s) failed: %s' % (name, str(e)), xbmc.LOGERROR)
        except Exception:
            pass
        # Return a dict with default structure for the specific storage type
        if name == 'liked_songs':
            return {'pid': 0, 'ids': []}
        elif name == 'account':
             return {'uid': '', 'logined': True, 'first_run': True}
        elif name == 'time_machine':
            return {'weeks': []}
        else:
            # Return a plain dict as a non-persistent fallback for other storage types
            return {}


account = safe_get_storage('account')
if 'uid' not in account:
    account['uid'] = ''
if 'logined' not in account:
    account['logined'] = True
if 'first_run' not in account:
    account['first_run'] = True

music = NetEase()

PROFILE = xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
qrcode_path = os.path.join(PROFILE, 'qrcode')


def delete_files(path):
    files = os.listdir(path)
    for f in files:
        f_path = os.path.join(path, f)
        if os.path.isdir(f_path):
            delete_files(f_path)
        else:
            os.remove(f_path)


def caculate_size(path):
    count = 0
    size = 0
    files = os.listdir(path)
    for f in files:
        f_path = os.path.join(path, f)
        if os.path.isdir(f_path):
            count_, size_ = caculate_size(f_path)
            count += count_
            size += size_
        else:
            count += 1
            size += os.path.getsize(f_path)
    return count, size


@plugin.route('/delete_thumbnails/')
def delete_thumbnails():
    path = xbmc.translatePath('special://thumbnails')
    count, size = caculate_size(path)
    dialog = xbmcgui.Dialog()
    result = dialog.yesno('删除缩略图', '一共 {} 个文件，{} MB，确认删除吗？'.format(
        count, B2M(size)), '取消', '确认')
    if not result:
        return
    delete_files(path)
    dialog.notification('删除缩略图', '删除成功',
                        xbmcgui.NOTIFICATION_INFO, 800, False)


@plugin.route('/login/')
def login():
    keyboard = xbmc.Keyboard('', '请输入手机号或邮箱')
    keyboard.doModal()
    if (keyboard.isConfirmed()):
        username = keyboard.getText().strip()
        if not username:
            return
    else:
        return

    keyboard = xbmc.Keyboard('', '请输入密码')
    keyboard.doModal()
    if (keyboard.isConfirmed()):
        password = keyboard.getText().strip()
        if not username:
            return
    else:
        return
    password = hashlib.md5(password.encode('UTF-8')).hexdigest()

    login = music.login(username, password)
    if login['code'] == 200:
        account['logined'] = True
        account['uid'] = login['profile']['userId']
        dialog = xbmcgui.Dialog()
        dialog.notification('登录成功', '请重启软件以解锁更多功能',
                            xbmcgui.NOTIFICATION_INFO, 800, False)
    elif login['code'] == -1:
        dialog = xbmcgui.Dialog()
        dialog.notification('登录失败', '可能是网络问题',
                            xbmcgui.NOTIFICATION_INFO, 800, False)
    elif login['code'] == -462:
        dialog = xbmcgui.Dialog()
        dialog.notification('登录失败', '-462: 需要验证',
                            xbmcgui.NOTIFICATION_INFO, 800, False)
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification('登录失败', str(login['code']) + ': ' + login.get('msg', ''),
                            xbmcgui.NOTIFICATION_INFO, 800, False)


@plugin.route('/logout/')
def logout():
    account['logined'] = True
    account['uid'] = ''
    liked_songs = safe_get_storage('liked_songs')
    liked_songs['pid'] = 0
    liked_songs['ids'] = []
    COOKIE_PATH = os.path.join(PROFILE, 'cookie.txt')
    with open(COOKIE_PATH, 'w') as f:
        f.write('# Netscape HTTP Cookie File\n')
    dialog = xbmcgui.Dialog()
    dialog.notification(
        '退出成功', '账号退出成功', xbmcgui.NOTIFICATION_INFO, 800, False)


#limit = int(xbmcplugin.getSetting(int(sys.argv[1]),'number_of_songs_per_page'))
limit = xbmcplugin.getSetting(int(sys.argv[1]), 'number_of_songs_per_page')
if limit == '':
    limit = 100
else:
    limit = int(limit)

quality = xbmcplugin.getSetting(int(sys.argv[1]), 'quality')
if quality == '0':
    level = 'standard'
elif quality == '1':
    level = 'higher'
elif quality == '2':
    level = 'exhigh'
elif quality == '3':
    level = 'lossless'
elif quality == '4':
    level = 'hires'
elif quality == '5':
    level = 'jyeffect'
elif quality == '6':
    level = 'sky'
elif quality == '7':
    level = 'jymaster'
elif quality == '8':
    level = 'dolby'
else:
    level = 'standard'

resolution = xbmcplugin.getSetting(int(sys.argv[1]), 'resolution')
if resolution == '0':
    r = 240
elif resolution == '1':
    r = 480
elif resolution == '2':
    r = 720
elif resolution == '3':
    r = 1080
else:
    r = 720


def tag(info, color='red'):
    return '[COLOR ' + color + ']' + info + '[/COLOR]'


def trans_num(num):
    if num > 100000000:
        return str(round(num/100000000, 1)) + '亿'
    elif num > 10000:
        return str(round(num/10000, 1)) + '万'
    else:
        return str(num)


def trans_time(t):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t//1000))


def trans_date(t):
    return time.strftime('%Y-%m-%d', time.localtime(t//1000))


def B2M(size):
    return str(round(size/1048576, 1))


def get_songs(songs, privileges=[], picUrl=None, source=''):
    datas = []
    for i in range(len(songs)):
        song = songs[i]

        # song data
        if 'song' in song:
            song = song['song']
        # 云盘
        elif 'simpleSong' in song:
            tempSong = song
            song = song['simpleSong']
        elif 'songData' in song:
            song = song['songData']
        elif 'mainSong' in song:
            song = song['mainSong']
        data = {}

        # song id
        if 'id' in song:
            data['id'] = song['id']
        elif 'songId' in song:
            data['id'] = song['songId']
        data['name'] = song['name']

        # mv id
        if 'mv' in song:
            data['mv_id'] = song['mv']
        elif 'mvid' in song:
            data['mv_id'] = song['mvid']
        elif 'mv_id' in song:
            data['mv_id'] = song['mv_id']

        artist = ""
        artists = []
        data['picUrl'] = None
        if 'ar' in song:
            if song['ar'] is not None:
                artist = "/".join([a["name"]
                                  for a in song["ar"] if a["name"] is not None])
                artists = [[a['name'], a['id']] for a in song["ar"] if a["name"] is not None]
                if artist == "" and "pc" in song:
                    artist = "未知艺术家" if song["pc"]["ar"] is None else song["pc"]["ar"]

                if picUrl is not None:
                    data['picUrl'] = picUrl
                elif 'picUrl' in song['ar'] and song['ar']['picUrl'] is not None:
                    data['picUrl'] = song['ar']['picUrl']
                elif 'img1v1Url' in song['ar'] and song['ar']['img1v1Url'] is not None:
                    data['picUrl'] = song['ar']['img1v1Url']
            else:
                if 'simpleSong' in tempSong and 'artist' in tempSong and tempSong['artist'] != '':
                    artist = tempSong['artist']
                else:
                    artist = "未知艺术家"

        elif 'artists' in song:
            artists = [[a['name'], a['id']] for a in song["artists"]]
            artist = "/".join([a["name"] for a in song["artists"]])

            if picUrl is not None:
                data['picUrl'] = picUrl
            elif 'picUrl' in song['artists'][0] and song['artists'][0]['picUrl'] is not None:
                data['picUrl'] = song['artists'][0]['picUrl']
            elif 'img1v1Url' in song['artists'][0] and song['artists'][0]['img1v1Url'] is not None:
                data['picUrl'] = song['artists'][0]['img1v1Url']
        else:
            artist = "未知艺术家"
            artists = []
            # if 'simpleSong' in tempSong and 'ar' not in song and 'artist' in tempSong and tempSong['artist']!='':
            #     artist = tempSong['artist']
            # else:
            #     artist = "未知艺术家"
        data['artist'] = artist
        data['artists'] = artists

        if "al" in song:
            if song["al"] is not None:
                album_name = song["al"]["name"]
                album_id = song["al"]["id"]
                if 'picUrl' in song['al']:
                    data['picUrl'] = song['al']['picUrl']
            else:
                if 'simpleSong' in tempSong and 'album' in tempSong and tempSong['album'] != '':
                    album_name = tempSong['album']
                    album_id = 0
                else:
                    album_name = "未知专辑"
                    album_id = 0

        elif "album" in song:
            if song["album"] is not None:
                album_name = song["album"]["name"]
                album_id = song["album"]["id"]
            else:
                album_name = "未知专辑"
                album_id = 0

            if 'picUrl' in song['album']:
                data['picUrl'] = song['album']['picUrl']

        data['album_name'] = album_name
        data['album_id'] = album_id

        if 'alia' in song and song['alia'] is not None and len(song['alia']) > 0:
            data['alia'] = song['alia'][0]

        if 'cd' in song:
            data['disc'] = song['cd']
        elif 'disc' in song:
            data['disc'] = song['disc']
        else:
            data['disc'] = 1

        if 'no' in song:
            data['no'] = song['no']
        else:
            data['no'] = 1

        if 'dt' in song:
            data['dt'] = song['dt']
        elif 'duration' in song:
            data['dt'] = song['duration']

        if 'privilege' in song:
            privilege = song['privilege']
        elif len(privileges) > 0:
            privilege = privileges[i]
        else:
            privilege = None

        # 规范化 privilege，确保为 dict（避免后续直接下标访问导致 NoneType 错误）
        data['privilege'] = privilege or {}

        # 搜索歌词（安全访问 lyrics 字段）
        if source == 'search_lyric':
            lyrics = song.get('lyrics')
            if lyrics:
                data['lyrics'] = lyrics
                data['second_line'] = ''
                txt = lyrics.get('txt', '')

                index_list = [m.start() for m in re.finditer('\n', txt)]
                temps = []
                for words in lyrics.get('range', []):
                    first = words.get('first')
                    second = words.get('second')
                    if first is None or second is None:
                        continue
                    left = -1
                    right = -1
                    for index in range(len(index_list)):
                        if index_list[index] <= first:
                            left = index
                        if index_list[index] >= second:
                            right = index
                            break
                    temps.append({'first': first, 'second': second,
                                 'left': left, 'right': right})
                skip = []
                for index in range(len(temps)):
                    if index in skip:
                        break
                    line = ''
                    if temps[index]['left'] == -1:
                        line += txt[0:temps[index]['first']]
                    else:
                        line += txt[index_list[temps[index]['left']] + 1:temps[index]['first']]
                    line += tag(txt[temps[index]['first']: temps[index]['second']], 'blue')

                    for index2 in range(index+1, len(temps)):
                        if temps[index2]['left'] == temps[index]['left']:
                            line += txt[temps[index2-1]['second']: temps[index2]['first']]
                            line += tag(txt[temps[index2]['first']: temps[index2]['second']], 'blue')
                            skip.append(index2)
                        else:
                            break
                    if temps[index]['right'] == -1:
                        line += txt[temps[index]['second']: len(txt)]
                    else:
                        line += txt[temps[index]['second']: index_list[temps[index]['right']]] + '...'

                    data['second_line'] += line
        else:
            if xbmcplugin.getSetting(int(sys.argv[1]), 'show_album_name') == 'true':
                data['second_line'] = data['album_name']
        datas.append(data)
    return datas


def get_songs_items(datas, privileges=[], picUrl=None, offset=0, getmv=True, source='', sourceId=0, enable_index=True):
    songs = get_songs(datas, privileges, picUrl, source)
    items = []
    for play in songs:
        # 隐藏不能播放的歌曲（安全检查 privilege 是否为 None）
        priv = play.get('privilege') or {}
        if priv.get('pl', None) == 0 and xbmcplugin.getSetting(int(sys.argv[1]), 'hide_songs') == 'true':
            continue
        # 显示序号
        if xbmcplugin.getSetting(int(sys.argv[1]), 'show_index') == 'true' and enable_index:
            offset += 1
            if offset < 10:
                str_offset = '0' + str(offset) + '.'
            else:
                str_offset = str(offset) + '.'
        else:
            str_offset = ''

        ar_name = play['artist']

        mv_id = play['mv_id']
        song_naming_format = xbmcplugin.getSetting(int(sys.argv[1]), 'song_naming_format')
        if song_naming_format == '0':
            label = str_offset + ar_name + ' - ' + play['name']
        elif song_naming_format == '1':
            label = str_offset + play['name'] + ' - ' + ar_name
        elif song_naming_format == '2':
            label = str_offset + play['name']
        else:
            label = str_offset + ar_name + ' - ' + play['name']
        if 'alia' in play:
            label += tag('('+play['alia']+')', 'gray')

        st = priv.get('st')
        if st is not None and st < 0:
            label = tag(label, 'grey')
        liked_songs = safe_get_storage('liked_songs')
        if play['id'] in liked_songs['ids'] and xbmcplugin.getSetting(int(sys.argv[1]), 'like_tag') == 'true':
            label = tag('♥ ') + label
        # 仅当 privilege 存在键时再显示相关标签
        if priv:
            st2 = priv.get('st')
            if st2 is not None and st2 < 0:
                label = tag(label, 'grey')
            fee = priv.get('fee')
            if fee == 1 and xbmcplugin.getSetting(int(sys.argv[1]), 'vip_tag') == 'true':
                label += tag(' vip')
            if priv.get('cs') and xbmcplugin.getSetting(int(sys.argv[1]), 'cloud_tag') == 'true':
                label += ' ☁'
            flag = priv.get('flag', 0)
            if (flag & 64) > 0 and xbmcplugin.getSetting(int(sys.argv[1]), 'exclusive_tag') == 'true':
                label += tag(' 独家')
            # SQ 标记
            if xbmcplugin.getSetting(int(sys.argv[1]), 'sq_tag') == 'true':
                play_max = priv.get('playMaxBrLevel')
                if play_max:
                    if play_max == 'hires':
                        label += tag(' Hi-Res')
                    elif play_max == 'lossless':
                        label += tag(' SQ')
                    elif play_max == 'jyeffect':
                        label += tag(' 环绕声')
                    elif play_max == 'sky':
                        label += tag(' 沉浸声')
                    elif play_max == 'jymaster':
                        label += tag(' 超清母带')
                    elif play_max == 'dolby':
                        label += tag(' 杜比全景声')
                elif priv.get('maxbr', 0) >= 999000:
                    label += tag(' SQ')
            # payed: 0 未付费 | 3 付费单曲 | 5 付费专辑
            if priv.get('preSell') == True and xbmcplugin.getSetting(int(sys.argv[1]), 'presell_tag') == 'true':
                label += tag(' 预售')
            elif fee == 4 and priv.get('pl') == 0 and xbmcplugin.getSetting(int(sys.argv[1]), 'pay_tag') == 'true':
                label += tag(' 付费')
        if mv_id > 0 and xbmcplugin.getSetting(int(sys.argv[1]), 'mv_tag') == 'true':
            label += tag(' MV', 'green')

        if 'second_line' in play and play['second_line']:
            label += '\n' + play['second_line']
        context_menu = []
        if play['artists']:
            context_menu.append(('跳转到歌手: ' + play['artist'], 'RunPlugin(%s)' % plugin.url_for('to_artist', artists=json.dumps(play['artists']))))
        if play['album_name'] and play['album_id']:
            context_menu.append(('跳转到专辑: ' + play['album_name'], 'Container.Update(%s)' % plugin.url_for('album', id=play['album_id'])))
        if mv_id > 0 and xbmcplugin.getSetting(int(sys.argv[1]), 'mvfirst') == 'true' and getmv:
            context_menu.extend([
                ('播放歌曲', 'RunPlugin(%s)' % plugin.url_for('song_contextmenu', action='play_song', meida_type='song',
                 song_id=str(play['id']), mv_id=str(mv_id), sourceId=str(sourceId), dt=str(play['dt']//1000))),
                ('收藏到歌单', 'RunPlugin(%s)' % plugin.url_for('song_contextmenu', action='sub_playlist', meida_type='song',
                 song_id=str(play['id']), mv_id=str(mv_id), sourceId=str(sourceId), dt=str(play['dt']//1000))),
                ('收藏到视频歌单', 'RunPlugin(%s)' % plugin.url_for('song_contextmenu', action='sub_video_playlist', meida_type='song',
                 song_id=str(play['id']), mv_id=str(mv_id), sourceId=str(sourceId), dt=str(play['dt']//1000))),
            ])
            items.append({
                'label': label,
                'path': plugin.url_for('play', meida_type='mv', song_id=str(play['id']), mv_id=str(mv_id), sourceId=str(sourceId), dt=str(play['dt']//1000)),
                'is_playable': True,
                'icon': play.get('picUrl', None),
                'thumbnail': play.get('picUrl', None),
                'context_menu': context_menu,
                'info': {
                    'mediatype': 'video',
                    'title': play['name'],
                    'album': play['album_name'],
                },
                'info_type': 'video',
            })
        else:
            context_menu.extend([
                ('收藏到歌单', 'RunPlugin(%s)' % plugin.url_for('song_contextmenu', action='sub_playlist', meida_type='song',
                 song_id=str(play['id']), mv_id=str(mv_id), sourceId=str(sourceId), dt=str(play['dt']//1000))),
                ('歌曲ID:'+str(play['id']), ''),
            ])

            if mv_id > 0:
                context_menu.append(('收藏到视频歌单', 'RunPlugin(%s)' % plugin.url_for('song_contextmenu', action='sub_video_playlist',
                                    meida_type='song', song_id=str(play['id']), mv_id=str(mv_id), sourceId=str(sourceId), dt=str(play['dt']//1000))))
                context_menu.append(('播放MV', 'RunPlugin(%s)' % plugin.url_for('song_contextmenu', action='play_mv', meida_type='song', song_id=str(
                    play['id']), mv_id=str(mv_id), sourceId=str(sourceId), dt=str(play['dt']//1000))))

            # 歌曲不能播放时播放MV
            if priv and priv.get('st') is not None and priv.get('st') < 0 and mv_id > 0 and xbmcplugin.getSetting(int(sys.argv[1]), 'auto_play_mv') == 'true':
                items.append({
                    'label': label,
                    'path': plugin.url_for('play', meida_type='song', song_id=str(play['id']), mv_id=str(mv_id), sourceId=str(sourceId), dt=str(play['dt']//1000)),
                    'is_playable': True,
                    'icon': play.get('picUrl', None),
                    'thumbnail': play.get('picUrl', None),
                    'context_menu': context_menu,
                    'info': {
                        'mediatype': 'video',
                        'title': play['name'],
                        'album': play['album_name'],
                    },
                    'info_type': 'video',
                })
            else:
                if source == 'recommend_songs':
                    items.append({
                        'label': label,
                        'path': plugin.url_for('play_recommend_songs', song_id=str(play['id']), mv_id=str(mv_id), dt=str(play['dt']//1000)),
                        'is_playable': True,
                        'icon': play.get('picUrl', None),
                        'thumbnail': play.get('picUrl', None),
                        'fanart': play.get('picUrl', None),
                        'context_menu': context_menu,
                        'info': {
                            'mediatype': 'music',
                            'title': play['name'],
                            'artist': ar_name,
                            'album': play['album_name'],
                            'tracknumber': play['no'],
                            'discnumber': play['disc'],
                            'duration': play['dt']//1000,
                            'dbid': play['id'],
                        },
                        'info_type': 'music',
                        'properties': {
                            'ncmid': str(play['id'])
                        },
                    })
                elif source == 'playlist':
                    items.append({
                        'label': label,
                        'path': plugin.url_for('play_playlist_songs', playlist_id=str(sourceId), song_id=str(play['id']), mv_id=str(mv_id), dt=str(play['dt']//1000)),
                        'is_playable': True,
                        'icon': play.get('picUrl', None),
                        'thumbnail': play.get('picUrl', None),
                        'fanart': play.get('picUrl', None),
                        'context_menu': context_menu,
                        'info': {
                            'mediatype': 'music',
                            'title': play['name'],
                            'artist': ar_name,
                            'album': play['album_name'],
                            'tracknumber': play['no'],
                            'discnumber': play['disc'],
                            'duration': play['dt']//1000,
                            'dbid': play['id'],
                        },
                        'info_type': 'music',
                        'properties': {
                            'ncmid': str(play['id'])
                        },
                    })
                else:
                    items.append({
                        'label': label,
                        'path': plugin.url_for('play', meida_type='song', song_id=str(play['id']), mv_id=str(mv_id), sourceId=str(sourceId), dt=str(play['dt']//1000)),
                        'is_playable': True,
                        'icon': play.get('picUrl', None),
                        'thumbnail': play.get('picUrl', None),
                        'fanart': play.get('picUrl', None),
                        'context_menu': context_menu,
                        'info': {
                            'mediatype': 'music',
                            'title': play['name'],
                            'artist': ar_name,
                            'album': play['album_name'],
                            'tracknumber': play['no'],
                            'discnumber': play['disc'],
                            'duration': play['dt']//1000,
                            'dbid': play['id'],
                        },
                        'info_type': 'music',
                        'properties': {
                            'ncmid': str(play['id'])
                        },
                    })
    return items


@plugin.route('/to_artist/<artists>/')
def to_artist(artists):
    artists = json.loads(artists)
    if len(artists) == 1:
        xbmc.executebuiltin('Container.Update(%s)' % plugin.url_for('artist', id=artists[0][1]))
        return
    sel = xbmcgui.Dialog().select('选择要跳转的歌手', [a[0] for a in artists])
    if sel < 0:
        return
    xbmc.executebuiltin('Container.Update(%s)' % plugin.url_for('artist', id=artists[sel][1]))

@plugin.route('/song_contextmenu/<action>/<meida_type>/<song_id>/<mv_id>/<sourceId>/<dt>/')
def song_contextmenu(action, meida_type, song_id, mv_id, sourceId, dt):
    if action == 'sub_playlist':
        ids = []
        names = []
        names.append('+ 新建歌单')
        playlists = music.user_playlist(
            account['uid'], includeVideo=False).get('playlist', [])
        for playlist in playlists:
            if str(playlist['userId']) == str(account['uid']):
                ids.append(playlist['id'])
                names.append(playlist['name'])
        dialog = xbmcgui.Dialog()
        ret = dialog.contextmenu(names)
        if ret == 0:
            keyboard = xbmc.Keyboard('', '请输入歌单名称')
            keyboard.doModal()
            if (keyboard.isConfirmed()):
                name = keyboard.getText()
            else:
                return

            create_result = music.playlist_create(name)
            if create_result['code'] == 200:
                playlist_id = create_result['id']
            else:
                dialog = xbmcgui.Dialog()
                dialog.notification(
                    '创建失败', '歌单创建失败', xbmcgui.NOTIFICATION_INFO, 800, False)
        elif ret >= 1:
            playlist_id = ids[ret-1]

        if ret >= 0:
            result = music.playlist_tracks(playlist_id, [song_id], op='add')
            msg = ''
            if result['code'] == 200:
                msg = '收藏成功'
                liked_songs = safe_get_storage('liked_songs')
                if liked_songs['pid'] == playlist_id:
                    liked_songs['ids'].append(int(song_id))
                xbmc.executebuiltin('Container.Refresh')
            elif 'message' in result and result['message'] is not None:
                msg = str(result['code'])+'错误:'+result['message']
            else:
                msg = str(result['code'])+'错误'
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '收藏', msg, xbmcgui.NOTIFICATION_INFO, 800, False)
    elif action == 'sub_video_playlist':
        ids = []
        names = []
        playlists = music.user_playlist(
            account['uid'], includeVideo=True).get("playlist", [])
        for playlist in playlists:
            if str(playlist['userId']) == str(account['uid']) and playlist['specialType'] == 200:
                ids.append(playlist['id'])
                names.append(playlist['name'])
        dialog = xbmcgui.Dialog()
        ret = dialog.contextmenu(names)
        if ret >= 0:
            result = music.playlist_add(ids[ret], [mv_id])
            msg = ''
            if result['code'] == 200:
                msg = '收藏成功'
            elif 'msg' in result:
                msg = result['message']
            else:
                msg = '收藏失败'
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '收藏', msg, xbmcgui.NOTIFICATION_INFO, 800, False)
    elif action == 'play_song':
        songs = music.songs_url_v1([song_id], level=level).get("data", [])
        urls = [song['url'] for song in songs]
        url = urls[0]
        if url is None:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '播放', '该歌曲无法播放', xbmcgui.NOTIFICATION_INFO, 800, False)
        else:
            xbmc.executebuiltin('PlayMedia(%s)' % url)
    elif action == 'play_mv':
        mv = music.mv_url(mv_id, r).get("data", {})
        url = mv.get('url')
        if url is None:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '播放', '该视频已删除', xbmcgui.NOTIFICATION_INFO, 800, False)
        else:
            xbmc.executebuiltin('PlayMedia(%s)' % url)


@plugin.route('/play/<meida_type>/<song_id>/<mv_id>/<sourceId>/<dt>/')
def play(meida_type, song_id, mv_id, sourceId, dt):
    if meida_type == 'mv':
        mv = music.mv_url(mv_id, r).get("data", {})
        url = mv.get('url')
        if url is None:
            dialog = xbmcgui.Dialog()
            dialog.notification('MV播放失败', '自动播放歌曲',
                                xbmcgui.NOTIFICATION_INFO, 800, False)

            songs = music.songs_url_v1([song_id], level=level).get("data", [])
            urls = [song['url'] for song in songs]
            if len(urls) == 0:
                url = None
            else:
                url = urls[0]
    elif meida_type == 'song':
        songs = music.songs_url_v1([song_id], level=level).get("data", [])
        urls = [song['url'] for song in songs]
        # 一般是网络错误
        if len(urls) == 0:
            url = None
        else:
            url = urls[0]
        if url is None:
            if int(mv_id) > 0 and xbmcplugin.getSetting(int(sys.argv[1]), 'auto_play_mv') == 'true':
                mv = music.mv_url(mv_id, r).get("data", {})
                url = mv['url']
                if url is not None:
                    msg = '该歌曲无法播放，自动播放MV'
                else:
                    msg = '该歌曲和MV无法播放'
            else:
                msg = '该歌曲无法播放'
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '播放失败', msg, xbmcgui.NOTIFICATION_INFO, 800, False)
        else:
            if xbmcplugin.getSetting(int(sys.argv[1]), 'upload_play_record') == 'true':
                music.daka(song_id, time=dt)
    elif meida_type == 'dj':
        result = music.dj_detail(song_id)
        song_id = result.get('program', {}).get('mainSong', {}).get('id')
        songs = music.songs_url_v1([song_id], level=level).get("data", [])
        urls = [song['url'] for song in songs]
        if len(urls) == 0:
            url = None
        else:
            url = urls[0]
        if url is None:
            msg = '该节目无法播放'
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '播放失败', msg, xbmcgui.NOTIFICATION_INFO, 800, False)
    elif meida_type == 'mlog':
        result = music.mlog_detail(mv_id, r)
        url = result.get('data', {}).get('resource', {}).get('content', {}).get('video', {}).get('urlInfo', {}).get('url')

    # else:
    #     music.daka(song_id,sourceId,dt)

    # 当通过皮肤小部件直接启动播放时，Kodi 可能不会携带原始列表项的 metadata。
    # 因此在此处构建一个包含信息的 ListItem 并显式设置 resolved url，确保播放器显示正确的歌曲/视频信息。
    try:
        listitem = None
        if url is not None:
            if meida_type == 'song':
                try:
                    resp = music.songs_detail([song_id])
                    song_info = resp.get('songs', [])[0]
                    title = song_info.get('name')
                    artists = song_info.get('ar') or song_info.get('artists') or []
                    artist = "/".join([a.get('name') for a in artists if a.get('name')])
                    album = (song_info.get('al') or song_info.get('album') or {}).get('name')
                    duration = song_info.get('dt') or song_info.get('duration')

                    listitem = xbmcgui.ListItem(label=title or '')
                    music_tag = listitem.getMusicInfoTag()
                    music_tag.setTitle(title or '')
                    music_tag.setArtist(artist or '')
                    music_tag.setAlbum(album or '')
                    music_tag.setDuration((duration // 1000) if isinstance(duration, int) else 0)
                    if song_id and str(song_id).isdigit():
                        music_tag.setDatabaseId(int(song_id))
                except Exception:
                    listitem = xbmcgui.ListItem()
            elif meida_type == 'mv':
                try:
                    # 尝试读取 mv 的简单信息（如有），否则构建最小 listitem
                    mv_detail = music.mv_url(mv_id, r).get('data', {})
                    title = mv_detail.get('name') or mv_detail.get('title') or ''
                    listitem = xbmcgui.ListItem(label=title)
                    video_tag = listitem.getVideoInfoTag()
                    video_tag.setTitle(title)
                except Exception:
                    listitem = xbmcgui.ListItem()
            elif meida_type == 'dj':
                try:
                    # dj 播放也可以使用 songs_detail 获取主曲目的信息
                    resp = music.songs_detail([song_id])
                    song_info = resp.get('songs', [])[0]
                    title = song_info.get('name')
                    artists = song_info.get('ar') or song_info.get('artists') or []
                    artist = "/".join([a.get('name') for a in artists if a.get('name')])
                    album = (song_info.get('al') or song_info.get('album') or {}).get('name')
                    duration = song_info.get('dt') or song_info.get('duration')

                    listitem = xbmcgui.ListItem(label=title or '')
                    music_tag = listitem.getMusicInfoTag()
                    music_tag.setTitle(title or '')
                    music_tag.setArtist(artist or '')
                    music_tag.setAlbum(album or '')
                    music_tag.setDuration((duration // 1000) if isinstance(duration, int) else 0)
                except Exception:
                    listitem = xbmcgui.ListItem()
            elif meida_type == 'mlog':
                try:
                    # mlog 可能返回较深的结构，尝试安全读取标题
                    mlog_detail = music.mlog_detail(mv_id, r).get('data', {})
                    title = mlog_detail.get('resource', {}).get('content', {}).get('video', {}).get('title') or ''
                    listitem = xbmcgui.ListItem(label=title)
                    video_tag = listitem.getVideoInfoTag()
                    video_tag.setTitle(title)
                except Exception:
                    listitem = xbmcgui.ListItem()
            else:
                listitem = xbmcgui.ListItem()
        else:
            listitem = xbmcgui.ListItem()
    except Exception:
        listitem = xbmcgui.ListItem()

    try:
        # 记录调试信息，帮助定位不可播放问题
        try:
            xbmc.log('plugin.audio.music163: resolving url for %s id=%s url=%s' % (str(meida_type), str(song_id), str(url)), xbmc.LOGDEBUG)
        except Exception:
            pass

        # 确保 ListItem 包含播放路径，否则 Kodi 会将其视为不可播放项
        try:
            if url is not None and hasattr(listitem, 'setPath'):
                listitem.setPath(url)
        except Exception:
            pass

        # 先尝试使用老的 xbmcswift2 wrapper 设置 resolved url（保证路径被识别），
        # 然后调用 xbmcplugin.setResolvedUrl 以传递 metadata（如果可用）。
        try:
            if url is not None:
                try:
                    plugin.set_resolved_url(url)
                except Exception:
                    # 不应阻止后续的 xbmcplugin.setResolvedUrl
                    pass
        except Exception:
            pass

        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)
    except Exception:
        # 回退到原有方式（兼容未知 xbmcswift2 版本）
        try:
            plugin.set_resolved_url(url)
        except Exception:
            pass


# 主目录
@plugin.route('/')
def index():
    # if account['first_run']:
    #     account['first_run'] = False
    #     xbmcgui.Dialog().ok('使用提示', '在设置中登录账号以解锁更多功能')
    items = []
    status = account['logined']

    liked_songs = safe_get_storage('liked_songs')
    if 'pid' not in liked_songs:
        liked_songs['pid'] = 0
    if 'ids' not in liked_songs:
        liked_songs['ids'] = []
    if xbmcplugin.getSetting(int(sys.argv[1]), 'like_tag') == 'true' and liked_songs['pid']:
        res = music.playlist_detail(liked_songs['pid'])
        if res['code'] == 200:
            liked_songs['ids'] = [s['id'] for s in res.get('playlist', {}).get('trackIds', [])]

    # 修改: 每日推荐不再检查登录状态
    if xbmcplugin.getSetting(int(sys.argv[1]), 'daily_recommend') == 'true':
        items.append(
            {'label': '每日推荐', 'path': plugin.url_for('recommend_songs')})
    # 修改: 私人FM不再检查登录状态
    if xbmcplugin.getSetting(int(sys.argv[1]), 'personal_fm') == 'true':
        items.append({'label': '私人FM', 'path': plugin.url_for('personal_fm')})
    # 修改: 我的歌单不再检查登录状态
    if xbmcplugin.getSetting(int(sys.argv[1]), 'my_playlists') == 'true':
        items.append({'label': '我的歌单', 'path': plugin.url_for(
            'user_playlists', uid=account['uid'])})
    # 修改: 我的收藏不再检查登录状态
    if xbmcplugin.getSetting(int(sys.argv[1]), 'sublist') == 'true':
        items.append({'label': '我的收藏', 'path': plugin.url_for('sublist')})
    # 修改: 推荐歌单不再检查登录状态
    if xbmcplugin.getSetting(int(sys.argv[1]), 'recommend_playlists') == 'true':
        items.append(
            {'label': '推荐歌单', 'path': plugin.url_for('recommend_playlists')})
    # 修改: 黑胶时光机不再检查登录状态
    if xbmcplugin.getSetting(int(sys.argv[1]), 'vip_timemachine') == 'true':
        items.append(
            {'label': '黑胶时光机', 'path': plugin.url_for('vip_timemachine')})
    if xbmcplugin.getSetting(int(sys.argv[1]), 'rank') == 'true':
        items.append({'label': '排行榜', 'path': plugin.url_for('toplists')})
    if xbmcplugin.getSetting(int(sys.argv[1]), 'hot_playlists') == 'true':
        items.append({'label': '热门歌单', 'path': plugin.url_for('hot_playlists', offset='0')})
    if xbmcplugin.getSetting(int(sys.argv[1]), 'top_artist') == 'true':
        items.append({'label': '热门歌手', 'path': plugin.url_for('top_artists')})
    if xbmcplugin.getSetting(int(sys.argv[1]), 'top_mv') == 'true':
        items.append(
            {'label': '热门MV', 'path': plugin.url_for('top_mvs', offset='0')})
    if xbmcplugin.getSetting(int(sys.argv[1]), 'search') == 'true':
        items.append({'label': '搜索', 'path': plugin.url_for('search')})
    # 修改: 我的云盘不再检查登录状态
    if xbmcplugin.getSetting(int(sys.argv[1]), 'cloud_disk') == 'true':
        items.append(
            {'label': '我的云盘', 'path': plugin.url_for('cloud', offset='0')})
    # 修改: 我的主页不再检查登录状态
    if xbmcplugin.getSetting(int(sys.argv[1]), 'home_page') == 'true':
        items.append(
            {'label': '我的主页', 'path': plugin.url_for('user', id=account['uid'])})
    if xbmcplugin.getSetting(int(sys.argv[1]), 'new_albums') == 'true':
        items.append(
            {'label': '新碟上架', 'path': plugin.url_for('new_albums', offset='0')})
    if xbmcplugin.getSetting(int(sys.argv[1]), 'new_albums') == 'true':
        items.append({'label': '新歌速递', 'path': plugin.url_for('new_songs')})
    if xbmcplugin.getSetting(int(sys.argv[1]), 'mlog') == 'true':
        items.append(
            {'label': 'Mlog', 'path': plugin.url_for('mlog_category')})

    # TuneHub 功能入口
    if xbmcplugin.getSetting(int(sys.argv[1]), 'tunehub_search') == 'true':
        items.append({'label': 'TuneHub 单平台搜索', 'path': plugin.url_for('tunehub_search')})
    if xbmcplugin.getSetting(int(sys.argv[1]), 'tunehub_aggregate_search') == 'true':
        items.append({'label': 'TuneHub 聚合搜索', 'path': plugin.url_for('tunehub_aggregate_search')})
    if xbmcplugin.getSetting(int(sys.argv[1]), 'tunehub_playlist') == 'true':
        items.append({'label': 'TuneHub 歌单', 'path': plugin.url_for('tunehub_playlist')})
    if xbmcplugin.getSetting(int(sys.argv[1]), 'tunehub_toplists') == 'true':
        items.append({'label': 'TuneHub 排行榜', 'path': plugin.url_for('tunehub_toplists')})

    return items


@plugin.route('/vip_timemachine/')
def vip_timemachine():
    time_machine = safe_get_storage('time_machine')
    items = []
    now = datetime.now()
    this_year_start = datetime(now.year, 1, 1)
    next_year_start = datetime(now.year + 1, 1, 1)
    this_year_start_timestamp = int(
        time.mktime(this_year_start.timetuple()) * 1000)
    this_year_end_timestamp = int(time.mktime(
        next_year_start.timetuple()) * 1000) - 1
    resp = music.vip_timemachine(
        this_year_start_timestamp, this_year_end_timestamp)

    if resp['code'] != 200:
        return items
    weeks = resp.get('data', {}).get('detail', [])
    time_machine['weeks'] = weeks
    for index, week in enumerate(weeks):
        start_date = time.strftime(
            "%m.%d", time.localtime(week['weekStartTime']//1000))
        end_date = time.strftime(
            "%m.%d", time.localtime(week['weekEndTime']//1000))
        title = week['data']['keyword'] + ' ' + \
            tag(start_date + '-' + end_date, 'red')

        if 'subTitle' in week['data'] and week['data']['subTitle']:
            second_line = ''
            subs = week['data']['subTitle'].split('##1')
            for i, sub in enumerate(subs):
                if i % 2 == 0:
                    second_line += tag(sub, 'gray')
                else:
                    second_line += tag(sub, 'blue')
            title += '\n' + second_line
        plot_info = ''
        plot_info += '[B]听歌数据:[/B]' + '\n'
        listenSongs = tag(str(week['data']['listenSongs']) + '首', 'pink')
        listenCount = tag(str(week['data']['listenWeekCount']) + '次', 'pink')
        listentime = ''
        t = week['data']['listenWeekTime']
        if t == 0:
            listentime += '0秒钟'
        else:
            if t >= 3600:
                listentime += str(t//3600) + '小时'
            if t % 3600 >= 0:
                listentime += str((t % 3600)//60) + '分钟'
            if t % 60 > 0:
                listentime += str(t % 60) + '秒钟'
        listentime = tag(listentime, 'pink')
        plot_info += '本周听歌{}，共听了{}\n累计时长{}\n'.format(
            listenSongs, listenCount, listentime)
        styles = (week['data'].get('listenCommonStyle', {})
                  or {}).get('styleDetailList', [])
        if styles:
            # if plot_info:
            #     plot_info += '\n'
            plot_info += '[B]常听曲风:[/B]' + '\n'
            for style in styles:
                plot_info += tag(style['styleName'], 'blue') + tag(' %.2f%%' %
                                                                   round(float(style['percent']) * 100, 2), 'pink') + '\n'
        emotions = (week['data'].get('musicEmotion', {})
                    or {}).get('subTitle', [])
        if emotions:
            # if plot_info:
            #     plot_info += '\n'
            plot_info += '[B]音乐情绪:[/B]' + '\n' + '你本周的音乐情绪是'
            emotions = [tag(e, 'pink') for e in emotions]
            if len(emotions) > 2:
                plot_info += '、'.join(emotions[:-1]) + \
                    '与' + emotions[-1] + '\n'
            else:
                plot_info += '与'.join(emotions) + '\n'
        items.append({
            'label': title,
            'path': plugin.url_for('vip_timemachine_week', index=index),
            'info': {
                'plot': plot_info
            },
            'info_type': 'video',
        })
    return items


@plugin.route('/vip_timemachine_week/<index>/')
def vip_timemachine_week(index):
    time_machine = safe_get_storage('time_machine')
    data = time_machine['weeks'][int(index)]['data']
    temp = []
    if 'song' in data:
        if 'tag' not in data['song'] or not data['song']['tag']:
            data['song']['tag'] = '高光歌曲'
        temp.append(data['song'])
    temp.extend(data.get('favoriteSongs', []))
    temp.extend((data.get('musicYear', {}) or {}).get('yearSingles', []))
    temp.extend((data.get('listenSingle', {}) or {}).get('singles', []))
    temp.extend(data.get('songInfos', []))
    songs_dict = {}
    for s in temp:
        if s['songId'] not in songs_dict:
            songs_dict[s['songId']] = s
        elif not songs_dict[s['songId']]['tag']:
            songs_dict[s['songId']]['tag'] = s['tag']
    ids = list(songs_dict.keys())
    songs = list(songs_dict.values())
    resp = music.songs_detail(ids)
    datas = resp['songs']
    privileges = resp['privileges']
    items = get_songs_items(datas, privileges=privileges, enable_index=False)
    for i, item in enumerate(items):
        if songs[i]['tag']:
            item['label'] = tag('[{}]'.format(
                songs[i]['tag']), 'pink') + item['label']

    return items


def qrcode_check():
    if not os.path.exists(qrcode_path):
        SUCCESS = xbmcvfs.mkdir(qrcode_path)
        if not SUCCESS:
            dialog = xbmcgui.Dialog()
            dialog.notification('失败', '目录创建失败，无法使用该功能',
                                xbmcgui.NOTIFICATION_INFO, 800, False)
            return False
        else:
            temp_path = os.path.join(qrcode_path, str(int(time.time()))+'.png')
            img = qrcode.make('temp_img')
            img.save(temp_path)

    _, files = xbmcvfs.listdir(qrcode_path)
    for file in files:
        xbmcvfs.delete(os.path.join(qrcode_path, file))
    return True


def check_login_status(key):
    for i in range(10):
        check_result = music.login_qr_check(key)
        if check_result['code'] == 803:
            account['logined'] = True
            resp = music.user_level()
            account['uid'] = resp['data']['userId']
            dialog = xbmcgui.Dialog()
            dialog.notification('登录成功', '请重启软件以解锁更多功能',
                                xbmcgui.NOTIFICATION_INFO, 800, False)
            xbmc.executebuiltin('Action(Back)')
            break
        time.sleep(3)
    xbmc.executebuiltin('Action(Back)')


@plugin.route('/qrcode_login/')
def qrcode_login():
    if not qrcode_check():
        return
    result = music.login_qr_key()
    key = result.get('unikey', '')
    login_path = 'https://music.163.com/login?codekey={}'.format(key)

    temp_path = os.path.join(qrcode_path, str(int(time.time()))+'.png')
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=20
    )
    qr.add_data(login_path)
    qr.make(fit=True)
    img = qr.make_image()
    img.save(temp_path)
    dialog = xbmcgui.Dialog()
    result = dialog.yesno('扫码登录', '请在在30秒内扫码登录', '取消', '确认')
    if not result:
        return
    xbmc.executebuiltin('ShowPicture(%s)' % temp_path)
    check_login_status(key)


# Mlog广场
@plugin.route('/mlog_category/')
def mlog_category():
    categories = {
        '广场': 1001,
        '热门': 2124301,
        'MV': 1002,
        '演唱': 4,
        '现场': 2,
        '情感': 2130301,
        'ACG': 2131301,
        '明星': 2132301,
        '演奏': 3,
        '生活': 8001,
        '舞蹈': 6001,
        '影视': 3001,
        '知识': 2125301,
    }

    items = []
    for category in categories:
        if categories[category] == 1001:
            items.append({'label': category, 'path': plugin.url_for(
                'mlog', cid=categories[category], pagenum=1)})
        else:
            items.append({'label': category, 'path': plugin.url_for(
                'mlog', cid=categories[category], pagenum=0)})
    return items


# Mlog
@plugin.route('/mlog/<cid>/<pagenum>/')
def mlog(cid, pagenum):
    items = []
    resp = music.mlog_socialsquare(cid, pagenum)
    mlogs = resp['data']['feeds']
    for video in mlogs:
        mid = video['id']
        if cid == '1002':
            path = plugin.url_for('play', meida_type='mv',
                                  song_id=0, mv_id=mid, sourceId=cid, dt=0)
        else:
            path = plugin.url_for('play', meida_type='mlog',
                                  song_id=0, mv_id=mid, sourceId=cid, dt=0)

        items.append({
            'label': video['resource']['mlogBaseData']['text'],
            'path': path,
            'is_playable': True,
            'icon': video['resource']['mlogBaseData']['coverUrl'],
            'thumbnail': video['resource']['mlogBaseData']['coverUrl'],
            'info': {
                'mediatype': 'video',
                'title': video['resource']['mlogBaseData']['text'],
                'duration': video['resource']['mlogBaseData']['duration']//1000
            },
            'info_type': 'video',
        })
    items.append({'label': tag('下一页', 'yellow'), 'path': plugin.url_for(
        'mlog', cid=cid, pagenum=int(pagenum)+1)})
    return items


# 热门MV
@plugin.route('/top_mvs/<offset>/')
def top_mvs(offset):
    offset = int(offset)
    result = music.top_mv(offset=offset, limit=limit)
    more = result['hasMore']
    mvs = result['data']
    items = get_mvs_items(mvs)
    if more:
        items.append({'label': tag('下一页', 'yellow'), 'path': plugin.url_for(
            'top_mvs', offset=str(offset+limit))})
    return items


# 新歌速递
@plugin.route('/new_songs/')
def new_songs():
    return get_songs_items(music.new_songs().get("data", []))


# 新碟上架
@plugin.route('/new_albums/<offset>/')
def new_albums(offset):
    offset = int(offset)
    result = music.new_albums(offset=offset, limit=limit)
    total = result.get('total', 0)
    albums = result.get('albums', [])
    items = get_albums_items(albums)
    if len(albums) + offset < total:
        items.append({'label': tag('下一页', 'yellow'), 'path': plugin.url_for(
            'new_albums', offset=str(offset+limit))})
    return items


# 排行榜
@plugin.route('/toplists/')
def toplists():
    items = get_playlists_items(music.toplists().get("list", []))
    return items


# 热门歌手
@plugin.route('/top_artists/')
def top_artists():
    return get_artists_items(music.top_artists().get("artists", []))


# 每日推荐
@plugin.route('/recommend_songs/')
def recommend_songs():
    songs = music.recommend_playlist().get('data', {}).get('dailySongs', [])
    return get_songs_items(songs, source='recommend_songs')

@plugin.route('/play_recommend_songs/<song_id>/<mv_id>/<dt>/')
def play_recommend_songs(song_id, mv_id, dt):
    # 获取所有每日推荐歌曲
    songs = music.recommend_playlist().get('data', {}).get('dailySongs', [])
    if not songs:
        dialog = xbmcgui.Dialog()
        dialog.notification('播放失败', '无法获取每日推荐歌曲列表', xbmcgui.NOTIFICATION_INFO, 800, False)
        return

    # 构建播放列表
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    playlist.clear()

    # 获取所有歌曲的ID和privileges（仅获取 metadata，延迟获取播放 URL）
    ids = [song['id'] for song in songs]
    resp = music.songs_detail(ids)
    datas = resp.get('songs', [])
    privileges = resp.get('privileges', [])

    selected_playlist_index = 0
    playlist_index = 0

    # 添加所有歌曲到播放列表（仅添加 plugin 路径，实际 URL 在 play() 中解析）
    for i, track in enumerate(datas):
        priv = privileges[i] if i < len(privileges) else {}
        if priv.get('pl', None) == 0 and xbmcplugin.getSetting(int(sys.argv[1]), 'hide_songs') == 'true':
            continue  # 跳过不可播放的歌曲

        # 检查是否为选中的歌曲
        if str(track['id']) == song_id:
            selected_playlist_index = playlist_index

        # 创建ListItem (保留元数据，但不包含实际播放 URL)
        artists = track.get('ar') or track.get('artists') or []
        artist = "/".join([a.get('name') for a in artists if a.get('name')])
        album = (track.get('al') or track.get('album') or {}).get('name')

        listitem = xbmcgui.ListItem(label=track['name'])
        music_tag = listitem.getMusicInfoTag()
        music_tag.setTitle(track['name'])
        music_tag.setArtist(artist)
        music_tag.setAlbum(album)
        music_tag.setDuration(track.get('dt', 0) // 1000)

        # 设置图片的URL和相关的属性
        picUrl = None
        if 'al' in track and track['al'] is not None and 'picUrl' in track['al']:
            picUrl = track['al']['picUrl']
        elif 'album' in track and track['album'] is not None and 'picUrl' in track['album']:
            picUrl = track['album']['picUrl']

        if picUrl is not None:
            listitem.setArt({'icon': picUrl, 'thumbnail': picUrl, 'fanart': picUrl})

        # 使用 plugin 路径延迟解析（Kodi 会在播放时调用插件的 play 路由）
        plugin_path = plugin.url_for('play', meida_type='song', song_id=str(track['id']), mv_id=str(0), sourceId='0', dt=str(track.get('dt', 0)//1000))
        playlist.add(plugin_path, listitem)
        playlist_index += 1

    # 播放播放列表从选中的歌曲开始
    if playlist.size() > 0:
        # 交给 Kodi 播放；Kodi 会为起始项调用本插件的 play 路由以进行解析
        xbmc.Player().play(playlist, startpos=selected_playlist_index)
    else:
        # 如果播放列表为空，显示错误
        dialog = xbmcgui.Dialog()
        dialog.notification('播放失败', '每日推荐中没有可播放的歌曲', xbmcgui.NOTIFICATION_INFO, 800, False)
        plugin.set_resolved_url(None)

    # 上传播放记录
    if xbmcplugin.getSetting(int(sys.argv[1]), 'upload_play_record') == 'true':
        music.daka(song_id, time=dt)


  

@plugin.route('/play_playlist_songs/<playlist_id>/<song_id>/<mv_id>/<dt>/')
def play_playlist_songs(playlist_id, song_id, mv_id, dt):
    # 获取歌单详情
    resp = music.playlist_detail(playlist_id)
    if not resp or 'playlist' not in resp:
        dialog = xbmcgui.Dialog()
        dialog.notification('播放失败', '无法获取歌单信息', xbmcgui.NOTIFICATION_INFO, 800, False)
        return

    # 获取所有歌曲
    datas = resp.get('playlist', {}).get('tracks', [])
    privileges = resp.get('privileges', [])
    trackIds = resp.get('playlist', {}).get('trackIds', [])

    # 处理超过1000首歌的情况
    songs_number = len(trackIds)
    if songs_number > len(datas):
        ids = [song['id'] for song in trackIds]
        resp2 = music.songs_detail(ids[len(datas):])
        datas.extend(resp2.get('songs', []))
        privileges.extend(resp2.get('privileges', []))

    # 构建播放列表
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    playlist.clear()

    selected_playlist_index = 0
    playlist_index = 0

    # 添加所有歌曲到播放列表（使用 plugin 路径，延迟在 play() 中解析实际播放 URL）
    for i, track in enumerate(datas):
        priv = privileges[i] if i < len(privileges) else {}
        if priv.get('pl', None) == 0 and xbmcplugin.getSetting(int(sys.argv[1]), 'hide_songs') == 'true':
            continue  # 跳过不可播放的歌曲

        # 检查是否为选中的歌曲
        if str(track['id']) == song_id:
            selected_playlist_index = playlist_index

        # 创建 ListItem（只填充元数据，不请求播放地址）
        artists = track.get('ar') or track.get('artists') or []
        artist = "/".join([a.get('name') for a in artists if a.get('name')])
        album = (track.get('al') or track.get('album') or {}).get('name')

        listitem = xbmcgui.ListItem(label=track['name'])
        music_tag = listitem.getMusicInfoTag()
        music_tag.setTitle(track['name'])
        music_tag.setArtist(artist)
        music_tag.setAlbum(album)
        music_tag.setDuration(track.get('dt', 0) // 1000)

        picUrl = None
        if 'al' in track and track['al'] is not None and 'picUrl' in track['al']:
            picUrl = track['al']['picUrl']
        elif 'album' in track and track['album'] is not None and 'picUrl' in track['album']:
            picUrl = track['album']['picUrl']
        if picUrl is not None:
            listitem.setArt({'icon': picUrl, 'thumbnail': picUrl, 'fanart': picUrl})

        plugin_path = plugin.url_for('play', meida_type='song', song_id=str(track['id']), mv_id=str(0), sourceId=str(playlist_id), dt=str(track.get('dt', 0)//1000))
        playlist.add(plugin_path, listitem)
        playlist_index += 1

    # 播放播放列表从选中的歌曲开始
    if playlist.size() > 0:
        # 直接交给 Kodi 播放；Kodi 会为起始项调用本插件的 play 路由以进行解析
        xbmc.Player().play(playlist, startpos=selected_playlist_index)
    else:
        # 如果播放列表为空，显示错误
        dialog = xbmcgui.Dialog()
        dialog.notification('播放失败', '歌单中没有可播放的歌曲', xbmcgui.NOTIFICATION_INFO, 800, False)
        plugin.set_resolved_url(None)

    # 上传播放记录
    if xbmcplugin.getSetting(int(sys.argv[1]), 'upload_play_record') == 'true':
        music.daka(song_id, time=dt)
    


# 历史日推
@plugin.route('/history_recommend_songs/<date>/')
def history_recommend_songs(date):
    return get_songs_items(music.history_recommend_detail(date).get('data', {}).get('songs', []))


def get_albums_items(albums):
    items = []
    for album in albums:
        if 'name' in album:
            name = album['name']
        elif 'albumName' in album:
            name = album['albumName']
        if 'size' in album:
            plot_info = '[COLOR pink]' + name + \
                '[/COLOR]  共' + str(album['size']) + '首歌\n'
        else:
            plot_info = '[COLOR pink]' + name + '[/COLOR]\n'
        if 'paidTime' in album and album['paidTime']:
            plot_info += '购买时间: ' + trans_time(album['paidTime']) + '\n'
        if 'type' in album and album['type']:
            plot_info += '类型: ' + album['type']
            if 'subType' in album and album['subType']:
                plot_info += ' - ' + album['subType'] + '\n'
            else:
                plot_info += '\n'
        if 'company' in album and album['company']:
            plot_info += '公司: ' + album['company'] + '\n'
        if 'id' in album:
            plot_info += '专辑id: ' + str(album['id'])+'\n'
            album_id = album['id']
        elif 'albumId' in album:
            plot_info += '专辑id: ' + str(album['albumId'])+'\n'
            album_id = album['albumId']
        if 'publishTime' in album and album['publishTime'] is not None:
            plot_info += '发行时间: '+trans_date(album['publishTime'])+'\n'
        if 'subTime' in album and album['subTime'] is not None:
            plot_info += '收藏时间: '+trans_date(album['subTime'])+'\n'
        if 'description' in album and album['description'] is not None:
            plot_info += album['description'] + '\n'
        if 'picUrl' in album:
            picUrl = album['picUrl']
        elif 'cover' in album:
            picUrl = album['cover']

        artists = [[a['name'], a['id']] for a in album['artists']]
        artists_str = '/'.join([a[0] for a in artists])
        context_menu = [
            ('跳转到歌手: ' + artists_str, 'RunPlugin(%s)' % plugin.url_for('to_artist', artists=json.dumps(artists)))
        ]
        items.append({
            'label': artists_str + ' - ' + name,
            'path': plugin.url_for('album', id=album_id),
            'icon': picUrl,
            'thumbnail': picUrl,
            'context_menu': context_menu,
            'info': {'plot': plot_info},
            'info_type': 'video',
        })
    return items


@plugin.route('/albums/<artist_id>/<offset>/')
def albums(artist_id, offset):
    offset = int(offset)
    result = music.artist_album(artist_id, offset=offset, limit=limit)
    more = result.get('more', False)
    albums = result.get('hotAlbums', [])
    items = get_albums_items(albums)
    if more:
        items.append({'label': tag('下一页', 'yellow'), 'path': plugin.url_for(
            'albums', artist_id=artist_id, offset=str(offset+limit))})
    return items


@plugin.route('/album/<id>/')
def album(id):
    result = music.album(id)
    return get_songs_items(result.get("songs", []), sourceId=id, picUrl=result.get('album', {}).get('picUrl', ''))


@plugin.route('/artist/<id>/')
def artist(id):
    items = [
        {'label': '热门50首', 'path': plugin.url_for('hot_songs', id=id)},
        {'label': '所有歌曲', 'path': plugin.url_for(
            'artist_songs', id=id, offset=0)},
        {'label': '专辑', 'path': plugin.url_for(
            'albums', artist_id=id, offset='0')},
        {'label': 'MV', 'path': plugin.url_for('artist_mvs', id=id, offset=0)},
    ]

    info = music.artist_info(id).get("artist", {})
    if 'accountId' in info:
        items.append({'label': '用户页', 'path': plugin.url_for(
            'user', id=info['accountId'])})

    if account['logined']:
        items.append(
            {'label': '相似歌手', 'path': plugin.url_for('similar_artist', id=id)})
    return items


@plugin.route('/similar_artist/<id>/')
def similar_artist(id):
    artists = music.similar_artist(id).get("artists", [])
    return get_artists_items(artists)


@plugin.route('/artist_mvs/<id>/<offset>/')
def artist_mvs(id, offset):
    offset = int(offset)
    result = music.artist_mvs(id, offset, limit)
    more = result.get('more', False)
    mvs = result.get("mvs", [])
    items = get_mvs_items(mvs)
    if more:
        items.append({'label': tag('下一页', 'yellow'), 'path': plugin.url_for(
            'albums', id=id, offset=str(offset+limit))})
    return items


@plugin.route('/hot_songs/<id>/')
def hot_songs(id):
    result = music.artists(id).get("hotSongs", [])
    ids = [a['id'] for a in result]
    resp = music.songs_detail(ids)
    datas = resp['songs']
    privileges = resp['privileges']
    return get_songs_items(datas, privileges=privileges)


@plugin.route('/artist_songs/<id>/<offset>/')
def artist_songs(id, offset):
    result = music.artist_songs(id, limit=limit, offset=offset)
    ids = [a['id'] for a in result.get('songs', [])]
    resp = music.songs_detail(ids)
    datas = resp['songs']
    privileges = resp['privileges']
    items = get_songs_items(datas, privileges=privileges)
    if result['more']:
        items.append({'label': '[COLOR yellow]下一页[/COLOR]', 'path': plugin.url_for(
            'artist_songs', id=id, offset=int(offset)+limit)})
    return items


# 我的收藏
@plugin.route('/sublist/')
def sublist():
    items = [
        {'label': '歌手', 'path': plugin.url_for('artist_sublist')},
        {'label': '专辑', 'path': plugin.url_for('album_sublist')},
        {'label': '视频', 'path': plugin.url_for('video_sublist')},
        {'label': '播单', 'path': plugin.url_for('dj_sublist', offset=0)},
        {'label': '我的数字专辑', 'path': plugin.url_for('digitalAlbum_purchased')},
        {'label': '已购单曲', 'path': plugin.url_for('song_purchased', offset=0)},
    ]
    return items


@plugin.route('/song_purchased/<offset>/')
def song_purchased(offset):
    result = music.single_purchased(offset=offset, limit=limit)
    ids = [a['songId'] for a in result.get('data', {}).get('list', [])]
    resp = music.songs_detail(ids)
    datas = resp['songs']
    privileges = resp['privileges']
    items = get_songs_items(datas, privileges=privileges)

    if result.get('data', {}).get('hasMore', False):
        items.append({'label': '[COLOR yellow]下一页[/COLOR]',
                     'path': plugin.url_for('song_purchased', offset=int(offset)+limit)})
    return items


@plugin.route('/dj_sublist/<offset>/')
def dj_sublist(offset):
    result = music.dj_sublist(offset=offset, limit=limit)
    items = get_djlists_items(result.get('djRadios', []))
    if result['hasMore']:
        items.append({'label': '[COLOR yellow]下一页[/COLOR]',
                     'path': plugin.url_for('dj_sublist', offset=int(offset)+limit)})
    return items


def get_djlists_items(playlists):
    items = []
    for playlist in playlists:
        context_menu = []
        plot_info = '[COLOR pink]' + playlist['name'] + \
            '[/COLOR]  共' + str(playlist['programCount']) + '个声音\n'
        if 'lastProgramCreateTime' in playlist and playlist['lastProgramCreateTime'] is not None:
            plot_info += '更新时间: ' + \
                trans_time(playlist['lastProgramCreateTime']) + '\n'
        if 'subCount' in playlist and playlist['subCount'] is not None:
            plot_info += '收藏人数: '+trans_num(playlist['subCount'])+'\n'
        plot_info += '播单id: ' + str(playlist['id'])+'\n'
        if 'dj' in playlist and playlist['dj'] is not None:
            plot_info += '创建用户: ' + \
                playlist['dj']['nickname'] + '  id: ' + \
                str(playlist['dj']['userId']) + '\n'
            context_menu.append(('跳转到用户: ' + playlist['dj']['nickname'], 'Container.Update(%s)' % plugin.url_for('user', id=playlist['dj']['userId'])))
        if 'createTime' in playlist and playlist['createTime'] is not None:
            plot_info += '创建时间: '+trans_time(playlist['createTime'])+'\n'
        if 'desc' in playlist and playlist['desc'] is not None:
            plot_info += playlist['desc'] + '\n'

        if 'coverImgUrl' in playlist and playlist['coverImgUrl'] is not None:
            img_url = playlist['coverImgUrl']
        elif 'picUrl' in playlist and playlist['picUrl'] is not None:
            img_url = playlist['picUrl']
        else:
            img_url = ''

        name = playlist['name']

        items.append({
            'label': name,
            'path': plugin.url_for('djlist', id=playlist['id'], offset=0),
            'icon': img_url,
            'thumbnail': img_url,
            'context_menu': context_menu,
            'info': {
                'plot': plot_info
            },
            'info_type': 'video',
        })
    return items


@plugin.route('/djlist/<id>/<offset>/')
def djlist(id, offset):
    if xbmcplugin.getSetting(int(sys.argv[1]), 'reverse_radio') == 'true':
        asc = False
    else:
        asc = True
    resp = music.dj_program(id, asc=asc, offset=offset, limit=limit)
    items = get_dj_items(resp.get('programs', []), id)
    if resp.get('more', False):
        items.append({'label': '[COLOR yellow]下一页[/COLOR]',
                     'path': plugin.url_for('djlist', id=id, offset=int(offset)+limit)})
    return items


def get_dj_items(songs, sourceId):
    items = []
    for play in songs:
        ar_name = play['dj']['nickname']

        label = play['name']

        listitem = xbmcgui.ListItem(label=label)
        music_tag = listitem.getMusicInfoTag()
        music_tag.setTitle(play['name'])
        music_tag.setArtist(ar_name)
        music_tag.setAlbum(play['radio']['name'])
        # music_tag.setTrackNumber(play['no'])
        # music_tag.setDiscNumber(play['disc'])
        # music_tag.setDuration(play['dt']//1000)
        # music_tag.setDatabaseId(play['id'])

        items.append({
            'label': label,
            'path': plugin.url_for('play', meida_type='dj', song_id=str(play['id']), mv_id=str(0), sourceId=str(sourceId), dt=str(play['duration']//1000)),
            'is_playable': True,
            'icon': play.get('coverUrl', None),
            'thumbnail': play.get('coverUrl', None),
            'fanart': play.get('coverUrl', None),
            'info': {
                'mediatype': 'music',
                'title': play['name'],
                'artist': ar_name,
                'album': play['radio']['name'],
                # 'tracknumber':play['no'],
                # 'discnumber':play['disc'],
                # 'duration': play['dt']//1000,
                # 'dbid':play['id'],
            },
            'info_type': 'music',
        })
    return items


@plugin.route('/digitalAlbum_purchased/')
def digitalAlbum_purchased():
    # items = []
    albums = music.digitalAlbum_purchased().get("paidAlbums", [])
    return get_albums_items(albums)


def get_mvs_items(mvs):
    items = []
    for mv in mvs:
        context_menu = []
        if 'artists' in mv:
            name = '/'.join([artist['name'] for artist in mv['artists']])
            artists = [[a['name'], a['id']] for a in mv['artists']]
            context_menu.append(('跳转到歌手: ' + name, 'RunPlugin(%s)' % plugin.url_for('to_artist', artists=json.dumps(artists))))
        elif 'artist' in mv:
            name = mv['artist']['name']
            artists = [[mv['artist']['name'], mv['artist']['id']]]
            context_menu.append(('跳转到歌手: ' + name, 'RunPlugin(%s)' % plugin.url_for('to_artist', artists=json.dumps(artists))))
        elif 'artistName' in mv:
            name = mv['artistName']
        else:
            name = ''
        mv_url = music.mv_url(mv['id'], r).get("data", {})
        url = mv_url.get('url')
        if 'cover' in mv:
            cover = mv['cover']
        elif 'imgurl' in mv:
            cover = mv['imgurl']
        else:
            cover = None
        # top_mvs->mv['subed']收藏;
        items.append({
            'label': name + ' - ' + mv['name'],
            'path': url,
            'is_playable': True,
            'icon': cover,
            'thumbnail': cover,
            'context_menu': context_menu,
            'info': {
                'mediatype': 'video',
                'title': mv['name'],
            },
            'info_type': 'video',
        })
    return items


def get_videos_items(videos):
    items = []
    for video in videos:
        type = video['type']  # MV:0 , video:1
        if type == 0:
            type = tag('[MV]')
            result = music.mv_url(video['vid'], r).get("data", {})
            url = result.get('url')
        else:
            type = ''
            result = music.video_url(video['vid'], r).get("urls", [])
            url = result[0]['url'] if len(result) > 0 and 'url' in result[0] else None
        ar_name = '&'.join([str(creator['userName'])
                           for creator in video['creator']])
        items.append({
            'label': type + ar_name + ' - ' + video['title'],
            'path': url,
            'is_playable': True,
            'icon': video['coverUrl'],
            'thumbnail': video['coverUrl'],
            # 'context_menu':context_menu,
            'info': {
                'mediatype': 'video',
                'title': video['title'],
                # 'duration':video['durationms']//1000
            },
            'info_type': 'video',
        })
    return items


@plugin.route('/playlist_contextmenu/<action>/<id>/')
def playlist_contextmenu(action, id):
    if action == 'subscribe':
        resp = music.playlist_subscribe(id)
        if resp['code'] == 200:
            title = '成功'
            msg = '收藏成功'
            xbmc.executebuiltin('Container.Refresh')
        elif resp['code'] == 401:
            title = '失败'
            msg = '不能收藏自己的歌单'
        elif resp['code'] == 501:
            title = '失败'
            msg = '已经收藏过该歌单了'
        else:
            title = '失败'
            msg = str(resp['code'])+': 未知错误'
        dialog = xbmcgui.Dialog()
        dialog.notification(title, msg, xbmcgui.NOTIFICATION_INFO, 800, False)
    elif action == 'unsubscribe':
        resp = music.playlist_unsubscribe(id)
        if resp['code'] == 200:
            title = '成功'
            msg = '取消收藏成功'
            dialog = xbmcgui.Dialog()
        dialog.notification(title, msg, xbmcgui.NOTIFICATION_INFO, 800, False)
    elif action == 'delete':
        resp = music.playlist_delete([id])
        if resp['code'] == 200:
            title = '成功'
            msg = '删除成功'
            xbmc.executebuiltin('Container.Refresh')
        else:
            title = '失败'
            msg = '删除失败'
        dialog = xbmcgui.Dialog()
        dialog.notification(title, msg, xbmcgui.NOTIFICATION_INFO, 800, False)


def get_playlists_items(playlists):
    items = []

    for playlist in playlists:
        if 'specialType' in playlist and playlist['specialType'] == 5:
            liked_songs = safe_get_storage('liked_songs')
            if liked_songs['pid']:
                liked_songs['pid'] = playlist['id']
            else:
                liked_songs['pid'] = playlist['id']
                res = music.playlist_detail(liked_songs['pid'])
                if res['code'] == 200:
                    liked_songs['ids'] = [s['id'] for s in res.get('playlist', {}).get('trackIds', [])]

        context_menu = []
        plot_info = '[COLOR pink]' + playlist['name'] + \
            '[/COLOR]  共' + str(playlist['trackCount']) + '首歌\n'
        if 'updateFrequency' in playlist and playlist['updateFrequency'] is not None:
            plot_info += '更新频率: ' + playlist['updateFrequency'] + '\n'
        if 'updateTime' in playlist and playlist['updateTime'] is not None:
            plot_info += '更新时间: ' + trans_time(playlist['updateTime']) + '\n'

        if 'subscribed' in playlist and playlist['subscribed'] is not None:
            if playlist['subscribed']:
                plot_info += '收藏状态: 已收藏\n'
                item = ('取消收藏', 'RunPlugin(%s)' % plugin.url_for(
                    'playlist_contextmenu', action='unsubscribe', id=playlist['id']))
                context_menu.append(item)
            else:
                if 'creator' in playlist and playlist['creator'] is not None and str(playlist['creator']['userId']) != account['uid']:
                    plot_info += '收藏状态: 未收藏\n'
                    item = ('收藏', 'RunPlugin(%s)' % plugin.url_for(
                        'playlist_contextmenu', action='subscribe', id=playlist['id']))
                    context_menu.append(item)
        else:
            if 'creator' in playlist and playlist['creator'] is not None and str(playlist['creator']['userId']) != account['uid']:
                item = ('收藏', 'RunPlugin(%s)' % plugin.url_for(
                    'playlist_contextmenu', action='subscribe', id=playlist['id']))
                context_menu.append(item)

        if 'subscribedCount' in playlist and playlist['subscribedCount'] is not None:
            plot_info += '收藏人数: '+trans_num(playlist['subscribedCount'])+'\n'
        if 'playCount' in playlist and playlist['playCount'] is not None:
            plot_info += '播放次数: '+trans_num(playlist['playCount'])+'\n'
        if 'playcount' in playlist and playlist['playcount'] is not None:
            plot_info += '播放次数: '+trans_num(playlist['playcount'])+'\n'
        plot_info += '歌单id: ' + str(playlist['id'])+'\n'
        if 'creator' in playlist and playlist['creator'] is not None:
            plot_info += '创建用户: '+playlist['creator']['nickname'] + \
                '  id: ' + str(playlist['creator']['userId']) + '\n'
            creator_name = playlist['creator']['nickname']
            creator_id = playlist['creator']['userId']
        else:
            creator_name = '网易云音乐'
            creator_id = 1
        context_menu.append(('跳转到用户: ' + creator_name, 'Container.Update(%s)' % plugin.url_for('user', id=creator_id)))
        if 'createTime' in playlist and playlist['createTime'] is not None:
            plot_info += '创建时间: '+trans_time(playlist['createTime'])+'\n'
        if 'description' in playlist and playlist['description'] is not None:
            plot_info += playlist['description'] + '\n'

        if 'coverImgUrl' in playlist and playlist['coverImgUrl'] is not None:
            img_url = playlist['coverImgUrl']
        elif 'picUrl' in playlist and playlist['picUrl'] is not None:
            img_url = playlist['picUrl']
        elif 'backgroundUrl' in playlist and playlist['backgroundUrl'] is not None:
            img_url = playlist['backgroundUrl']
        else:
            img_url = ''

        name = playlist['name']

        if playlist.get('privacy', 0) == 10:
            name += tag(' 隐私')

        if playlist.get('specialType', 0) == 300:
            name += tag(' 共享')

        if playlist.get('specialType', 0) == 200:
            name += tag(' 视频')
            ptype = 'video'
        else:
            ptype = 'normal'
        if 'creator' in playlist and playlist['creator'] is not None and str(playlist['creator']['userId']) == account['uid']:
            item = ('删除歌单', 'RunPlugin(%s)' % plugin.url_for(
                'playlist_contextmenu', action='delete', id=playlist['id']))
            context_menu.append(item)

        items.append({
            'label': name,
            'path': plugin.url_for('playlist', ptype=ptype, id=playlist['id']),
            'icon': img_url,
            'thumbnail': img_url,
            'context_menu': context_menu,
            'info': {
                'plot': plot_info
            },
            'info_type': 'video',
        })
    return items


@plugin.route('/video_sublist/')
def video_sublist():
    return get_videos_items(music.video_sublist().get("data", []))


@plugin.route('/album_sublist/')
def album_sublist():
    return get_albums_items(music.album_sublist().get("data", []))


def get_artists_items(artists):
    items = []
    for artist in artists:
        plot_info = '[COLOR pink]' + artist['name'] + '[/COLOR]'
        if 'musicSize' in artist and artist['musicSize']:
            plot_info += '  共' + str(artist['musicSize']) + '首歌\n'
        else:
            plot_info += '\n'

        if 'albumSize' in artist and artist['albumSize']:
            plot_info += '专辑数: ' + str(artist['albumSize']) + '\n'
        if 'mvSize' in artist and artist['mvSize']:
            plot_info += 'MV数: ' + str(artist['mvSize']) + '\n'
        plot_info += '歌手id: ' + str(artist['id'])+'\n'
        name = artist['name']
        if 'alias' in artist and artist['alias']:
            name += '('+artist['alias'][0]+')'
        elif 'trans' in artist and artist['trans']:
            name += '('+artist['trans']+')'

        items.append({
            'label': name,
            'path': plugin.url_for('artist', id=artist['id']),
            'icon': artist['picUrl'],
            'thumbnail': artist['picUrl'],
            'info': {'plot': plot_info},
            'info_type': 'video'
        })
    return items


def get_users_items(users):
    vip_level = ['', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖', '拾']
    items = []
    for user in users:
        plot_info = tag(user['nickname'], 'pink')
        if 'followed' in user:
            if user['followed'] == True:
                plot_info += '  [COLOR red]已关注[/COLOR]\n'
                context_menu = [('取消关注', 'RunPlugin(%s)' % plugin.url_for(
                    'follow_user', type='0', id=user['userId']))]
            else:
                plot_info += '\n'
                context_menu = [('关注该用户', 'RunPlugin(%s)' % plugin.url_for(
                    'follow_user', type='1', id=user['userId']))]
        else:
            plot_info += '\n'
        # userType: 0 普通用户 | 2 歌手 | 4 音乐人 | 10 官方账号 | 200 歌单达人 | 204 Mlog达人
        if user['vipType'] == 10:
            level_str = tag('音乐包', 'red')
            if user['userType'] == 4:
                plot_info += level_str + tag('  音乐人', 'red') + '\n'
            else:
                plot_info += level_str + '\n'
        elif user['vipType'] == 11:
            level = user['vipRights']['redVipLevel']
            if 'redplus' in user['vipRights'] and user['vipRights']['redplus'] is not None:
                level_str = tag('Svip·' + vip_level[level], 'gold')
            else:
                level_str = tag('vip·' + vip_level[level], 'red')
            if user['userType'] == 4:
                plot_info += level_str + tag('  音乐人', 'red') + '\n'
            else:
                plot_info += level_str + '\n'
        else:
            level_str = ''
            if user['userType'] == 4:
                plot_info += tag('音乐人', 'red') + '\n'

        if 'description' in user and user['description'] != '':
            plot_info += user['description'] + '\n'
        if 'signature' in user and user['signature']:
            plot_info += '签名: ' + user['signature'] + '\n'
        plot_info += '用户id: ' + str(user['userId'])+'\n'

        items.append({
            'label': user['nickname']+' '+level_str,
            'path': plugin.url_for('user', id=user['userId']),
            'icon': user['avatarUrl'],
            'thumbnail': user['avatarUrl'],
            'context_menu': context_menu,
            'info': {'plot': plot_info},
            'info_type': 'video',
        })
    return items


@plugin.route('/follow_user/<type>/<id>/')
def follow_user(type, id):
    # result = music.user_follow(type, id)
    if type == '1':
        result = music.user_follow(id)
        if 'code' in result:
            if result['code'] == 200:
                xbmcgui.Dialog().notification('关注用户', '关注成功', xbmcgui.NOTIFICATION_INFO, 800, False)
            elif result['code'] == 201:
                xbmcgui.Dialog().notification('关注用户', '您已关注过该用户',
                                              xbmcgui.NOTIFICATION_INFO, 800, False)
            elif result['code'] == 400:
                xbmcgui.Dialog().notification('关注用户', '不能关注自己',
                                              xbmcgui.NOTIFICATION_INFO, 800, False)
            elif 'mas' in result:
                xbmcgui.Dialog().notification(
                    '关注用户', result['msg'], xbmcgui.NOTIFICATION_INFO, 800, False)
    else:
        result = music.user_delfollow(id)
        if 'code' in result:
            if result['code'] == 200:
                xbmcgui.Dialog().notification('取消关注用户', '取消关注成功',
                                              xbmcgui.NOTIFICATION_INFO, 800, False)
            elif result['code'] == 201:
                xbmcgui.Dialog().notification('取消关注用户', '您已不关注该用户了',
                                              xbmcgui.NOTIFICATION_INFO, 800, False)
            elif 'mas' in result:
                xbmcgui.Dialog().notification(
                    '取消关注用户', result['msg'], xbmcgui.NOTIFICATION_INFO, 800, False)


@plugin.route('/user/<id>/')
def user(id):
    items = [
        {'label': '歌单', 'path': plugin.url_for('user_playlists', uid=id)},
        {'label': '听歌排行', 'path': plugin.url_for('play_record', uid=id)},
        {'label': '关注列表', 'path': plugin.url_for(
            'user_getfollows', uid=id, offset='0')},
        {'label': '粉丝列表', 'path': plugin.url_for(
            'user_getfolloweds', uid=id, offset=0)},
    ]

    if account['uid'] == id:
        items.append(
            {'label': '每日推荐', 'path': plugin.url_for('recommend_songs')})
        items.append(
            {'label': '历史日推', 'path': plugin.url_for('history_recommend_dates')})

    info = music.user_detail(id)
    if 'artistId' in info.get('profile', {}):
        items.append({'label': '歌手页', 'path': plugin.url_for(
            'artist', id=info['profile']['artistId'])})
    return items


@plugin.route('/history_recommend_dates/')
def history_recommend_dates():
    dates = music.history_recommend_recent().get('data', {}).get('dates', [])
    items = []
    for date in dates:
        items.append({'label': date, 'path': plugin.url_for(
            'history_recommend_songs', date=date)})
    return items


@plugin.route('/play_record/<uid>/')
def play_record(uid):
    items = [
        {'label': '最近一周', 'path': plugin.url_for(
            'show_play_record', uid=uid, type='1')},
        {'label': '全部时间', 'path': plugin.url_for(
            'show_play_record', uid=uid, type='0')},
    ]
    return items


@plugin.route('/show_play_record/<uid>/<type>/')
def show_play_record(uid, type):
    result = music.play_record(uid, type)
    code = result.get('code', -1)
    if code == -2:
        xbmcgui.Dialog().notification('无权访问', '由于对方设置，你无法查看TA的听歌排行',
                                      xbmcgui.NOTIFICATION_INFO, 800, False)
    elif code == 200:
        if type == '1':
            songs = result.get('weekData', [])
        else:
            songs = result.get('allData', [])
        items = get_songs_items(songs)

        # 听歌次数
        # for i in range(len(items)):
        #     items[i]['label'] = items[i]['label'] + ' [COLOR red]' + str(songs[i]['playCount']) + '[/COLOR]'

        return items


@plugin.route('/user_getfolloweds/<uid>/<offset>/')
def user_getfolloweds(uid, offset):
    result = music.user_getfolloweds(userId=uid, offset=offset, limit=limit)
    more = result['more']
    followeds = result['followeds']
    items = get_users_items(followeds)
    if more:
        # time = followeds[-1]['time']
        items.append({'label': tag('下一页', 'yellow'), 'path': plugin.url_for(
            'user_getfolloweds', uid=uid, offset=int(offset)+limit)})
    return items


@plugin.route('/user_getfollows/<uid>/<offset>/')
def user_getfollows(uid, offset):
    offset = int(offset)
    result = music.user_getfollows(uid, offset=offset, limit=limit)
    more = result['more']
    follows = result['follow']
    items = get_users_items(follows)
    if more:
        items.append({'label': '[COLOR yellow]下一页[/COLOR]', 'path': plugin.url_for(
            'user_getfollows', uid=uid, offset=str(offset+limit))})
    return items


@plugin.route('/artist_sublist/')
def artist_sublist():
    return get_artists_items(music.artist_sublist().get("data", []))


@plugin.route('/search/')
def search():
    items = [
        {'label': '综合搜索', 'path': plugin.url_for('sea', type='1018')},
        {'label': '单曲搜索', 'path': plugin.url_for('sea', type='1')},
        {'label': '歌手搜索', 'path': plugin.url_for('sea', type='100')},
        {'label': '专辑搜索', 'path': plugin.url_for('sea', type='10')},
        {'label': '歌单搜索', 'path': plugin.url_for('sea', type='1000')},
        {'label': '云盘搜索', 'path': plugin.url_for('sea', type='-1')},
        {'label': 'M V搜索', 'path': plugin.url_for('sea', type='1004')},
        {'label': '视频搜索', 'path': plugin.url_for('sea', type='1014')},
        {'label': '歌词搜索', 'path': plugin.url_for('sea', type='1006')},
        {'label': '用户搜索', 'path': plugin.url_for('sea', type='1002')},
        {'label': '播客搜索', 'path': plugin.url_for('sea', type='1009')},
    ]
    return items


@plugin.route('/sea/<type>/')
def sea(type):
    items = []
    keyboard = xbmc.Keyboard('', '请输入搜索内容')
    keyboard.doModal()
    if (keyboard.isConfirmed()):
        keyword = keyboard.getText()
    else:
        return

    # 搜索云盘
    if type == '-1':
        datas = []
        kws = keyword.lower().split(' ')
        while '' in kws:
            kws.remove('')
        if len(kws) == 0:
            pass
        else:
            result = music.cloud_songlist(offset=0, limit=2000)
            playlist = result.get('data', [])
            if result.get('hasMore', False):
                result = music.cloud_songlist(
                    offset=2000, limit=result['count']-2000)
                playlist.extend(result.get('data', []))

            for song in playlist:
                if 'ar' in song['simpleSong'] and song['simpleSong']['ar'] is not None and song['simpleSong']['ar'][0]['name'] is not None:
                    artist = " ".join(
                        [a["name"] for a in song['simpleSong']["ar"] if a["name"] is not None])
                else:
                    artist = song['artist']
                if 'al' in song['simpleSong'] and song['simpleSong']['al'] is not None and song['simpleSong']['al']['name'] is not None:
                    album = song['simpleSong']['al']['name']
                else:
                    album = song['album']
                if 'alia' in song['simpleSong'] and song['simpleSong']['alia'] is not None:
                    alia = " ".join(
                        [a for a in song['simpleSong']["alia"] if a is not None])
                else:
                    alia = ''
                # filename = song['fileName']

                matched = True
                for kw in kws:
                    if kw != '':
                        if (kw in song['simpleSong']['name'].lower()) or (kw in artist.lower()) or (kw in album.lower()) or (kw in alia.lower()):
                            pass
                        else:
                            matched = False
                            break
                if matched:
                    datas.append(song)
        if len(datas) > 0:
            items = get_songs_items(datas)
            return items
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '搜索', '无搜索结果', xbmcgui.NOTIFICATION_INFO, 800, False)

# TuneHub routes removed from here and will be reinserted at module level later
    result = music.search(keyword, stype=type).get("result", {})
    # 搜索单曲
    if type == '1':
        if 'songs' in result:
            sea_songs = result.get('songs', [])

            if xbmcplugin.getSetting(int(sys.argv[1]), 'hide_cover_songs') == 'true':
                filtered_songs = [
                    song for song in sea_songs if '翻自' not in song['name'] and 'cover' not in song['name'].lower()]
            else:
                filtered_songs = sea_songs

            ids = [a['id'] for a in filtered_songs]
            resp = music.songs_detail(ids)
            datas = resp['songs']
            privileges = resp['privileges']
            # 调整云盘歌曲的次序
            d1, d2, p1, p2 = [], [], [], []
            for i in range(len(datas)):
                if privileges[i]['cs']:
                    d1.append(datas[i])
                    p1.append(privileges[i])
                else:
                    d2.append(datas[i])
                    p2.append(privileges[i])
            d1.extend(d2)
            p1.extend(p2)
            datas = d1
            privileges = p1
            items = get_songs_items(datas, privileges=privileges)
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '搜索', '无搜索结果', xbmcgui.NOTIFICATION_INFO, 800, False)
            return
    # 搜索歌词
    if type == '1006':
        if 'songs' in result:
            sea_songs = result.get('songs', [])
            ids = [a['id'] for a in sea_songs]
            resp = music.songs_detail(ids)
            datas = resp['songs']
            privileges = resp['privileges']

            for i in range(len(datas)):
                datas[i]['lyrics'] = sea_songs[i]['lyrics']

            if xbmcplugin.getSetting(int(sys.argv[1]), 'hide_cover_songs') == 'true':
                filtered_datas = []
                filtered_privileges = []
                for i in range(len(datas)):
                    if '翻自' not in datas[i]['name'] and 'cover' not in datas[i]['name'].lower():
                        filtered_datas.append(datas[i])
                        filtered_privileges.append(privileges[i])
            else:
                filtered_datas = datas
                filtered_privileges = privileges

            items = get_songs_items(
                filtered_datas, privileges=filtered_privileges, source='search_lyric')
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '搜索', '无搜索结果', xbmcgui.NOTIFICATION_INFO, 800, False)
            return
    # 搜索专辑
    elif type == '10':
        if 'albums' in result:
            albums = result['albums']
            items.extend(get_albums_items(albums))
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '搜索', '无搜索结果', xbmcgui.NOTIFICATION_INFO, 800, False)
            return
    # 搜索歌手
    elif type == '100':
        if 'artists' in result:
            artists = result['artists']
            items.extend(get_artists_items(artists))
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '搜索', '无搜索结果', xbmcgui.NOTIFICATION_INFO, 800, False)
            return
    # 搜索用户
    elif type == '1002':
        if 'userprofiles' in result:
            users = result['userprofiles']
            items.extend(get_users_items(users))
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '搜索', '无搜索结果', xbmcgui.NOTIFICATION_INFO, 800, False)
            return
    # 搜索歌单
    elif type == '1000':
        if 'playlists' in result:
            playlists = result['playlists']
            items.extend(get_playlists_items(playlists))
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '搜索', '无搜索结果', xbmcgui.NOTIFICATION_INFO, 800, False)
            return
    # 搜索主播电台
    elif type == '1009':
        if 'djRadios' in result:
            playlists = result['djRadios']
            items.extend(get_djlists_items(playlists))
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '搜索', '无搜索结果', xbmcgui.NOTIFICATION_INFO, 800, False)
            return
    # 搜索MV
    elif type == '1004':
        if 'mvs' in result:
            mvs = result['mvs']
            items.extend(get_mvs_items(mvs))
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '搜索', '无搜索结果', xbmcgui.NOTIFICATION_INFO, 800, False)
            return
    # 搜索视频
    elif type == '1014':
        if 'videos' in result:
            videos = result['videos']
            items.extend(get_videos_items(videos))
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '搜索', '无搜索结果', xbmcgui.NOTIFICATION_INFO, 800, False)
            return
    # 综合搜索
    elif type == '1018':
        is_empty = True
        # 歌手
        if 'artist' in result:
            is_empty = False
            artist = result['artist']['artists'][0]
            item = get_artists_items([artist])[0]
            item['label'] = tag('[歌手]') + item['label']
            items.append(item)

        # 专辑
        if 'album' in result:
            is_empty = False
            album = result['album']['albums'][0]
            item = get_albums_items([album])[0]
            item['label'] = tag('[专辑]') + item['label']
            items.append(item)

        # 歌单
        if 'playList' in result:
            is_empty = False
            playList = result['playList']['playLists'][0]
            item = get_playlists_items([playList])[0]
            item['label'] = tag('[歌单]') + item['label']
            items.append(item)

        # MV & 视频
        if 'video' in result:
            is_empty = False
            # MV
            for video in result['video']['videos']:
                if video['type'] == 0:
                    mv_url = music.mv_url(video['vid'], r).get("data", {})
                    url = mv_url.get('url')
                    ar_name = '&'.join([str(creator['userName'])
                                       for creator in video['creator']])
                    name = tag('[M V]') + ar_name + '-' + video['title']
                    items.append({
                        'label': name,
                        'path': url,
                        'is_playable': True,
                        'icon': video['coverUrl'],
                        'thumbnail': video['coverUrl'],
                        'info': {
                            'mediatype': 'video',
                            'title': video['title'],
                            'duration': video['durationms']//1000
                        },
                        'info_type': 'video',
                    })
                    break
            # 视频
            for video in result['video']['videos']:
                if video['type'] == 1:
                    video_url = music.video_url(
                        video['vid'], r).get("urls", [])
                    url = video_url[0].get('url') if len(video_url) > 0 and isinstance(video_url[0], dict) else None
                    ar_name = '&'.join([str(creator['userName'])
                                       for creator in video['creator']])
                    name = tag('[视频]') + ar_name + '-' + video['title']
                    items.append({
                        'label': name,
                        'path': url,
                        'is_playable': True,
                        'icon': video['coverUrl'],
                        'thumbnail': video['coverUrl'],
                        'info': {
                            'mediatype': 'video',
                            'title': video['title'],
                            'duration': video['durationms']//1000
                        },
                        'info_type': 'video',
                    })
                    break
        # 单曲
        if 'song' in result:
            # is_empty = False
            # items.extend(get_songs_items([song['id'] for song in result['song']['songs']],getmv=False))
            sea_songs = result['song']['songs']
            if xbmcplugin.getSetting(int(sys.argv[1]), 'hide_cover_songs') == 'true':
                filtered_songs = [
                    song for song in sea_songs if '翻自' not in song['name'] and 'cover' not in song['name'].lower()]
            else:
                filtered_songs = sea_songs
            items.extend(get_songs_items(filtered_songs, getmv=False, enable_index=False))
            if len(items) > 0:
                is_empty = False

        if is_empty:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                '搜索', '无搜索结果', xbmcgui.NOTIFICATION_INFO, 800, False)
            return
    return items


@plugin.route('/personal_fm/')
def personal_fm():
    songs = []
    for i in range(10):
        songs.extend(music.personal_fm().get("data", []))
    return get_songs_items(songs)


@plugin.route('/tunehub_search/')
def tunehub_search():
    # 显示三个平台文件夹
    platforms = [
        {'source': 'netease', 'name': '网易云搜索'},
        {'source': 'qq', 'name': 'QQ音乐搜索'},
        {'source': 'kuwo', 'name': '酷我搜索'}
    ]
    items = []
    for platform in platforms:
        items.append({
            'label': platform['name'],
            'path': plugin.url_for('tunehub_search_platform', source=platform['source']),
            'is_playable': False,
        })
    return items

@plugin.route('/tunehub_search_platform/<source>/')
def tunehub_search_platform(source):
    keyboard = xbmc.Keyboard('', '请输入搜索关键词')
    keyboard.doModal()
    if not keyboard.isConfirmed():
        return
    keyword = keyboard.getText().strip()
    if not keyword:
        return

    resp = music.tunehub_search(source, keyword, limit=50, page=1)
    data = resp.get('data') if isinstance(resp, dict) else resp
    # 尝试从不同字段提取结果列表
    results = []
    if isinstance(data, dict):
        results = data.get('results') or data.get('data') or data.get('list') or []
    elif isinstance(data, list):
        results = data

    items = []
    for it in results:
        name = it.get('name') or it.get('title') or ''
        artist = it.get('artist') or it.get('artistName') or ''
        label = name + (' - ' + artist if artist else '')
        # 图片字段优先取 `pic`，再尝试其他常见字段
        pic = it.get('pic') or it.get('picUrl') or it.get('cover') or it.get('image') or it.get('thumbnail') or it.get('thumb') or ''
        item = {'label': label, 'path': plugin.url_for('tunehub_play', source=source, id=it.get('id'), br='320k')}
        if pic:
            item['thumbnail'] = pic
            item['icon'] = pic
            item['fanart'] = pic
        items.append(item)
    if not items:
        xbmcgui.Dialog().notification('TuneHub', '未找到结果', xbmcgui.NOTIFICATION_INFO, 800, False)
    return items


@plugin.route('/tunehub_aggregate_search/')
def tunehub_aggregate_search():
    keyboard = xbmc.Keyboard('', '请输入搜索关键词')
    keyboard.doModal()
    if not keyboard.isConfirmed():
        return
    keyword = keyboard.getText().strip()
    if not keyword:
        return
    resp = music.tunehub_aggregate_search(keyword, limit=50, page=1)
    data = resp.get('data') if isinstance(resp, dict) else {}

    # API 返回的聚合结果位于 data.results
    results = []
    if isinstance(data, dict):
        results = data.get('results') or data.get('data') or []
    elif isinstance(data, list):
        results = data

    items = []
    for it in results:
        name = it.get('name') or it.get('title') or ''
        artist = it.get('artist') or it.get('artistName') or ''
        platform = it.get('platform') or it.get('source') or ''
        label = name + (' - ' + artist if artist else '') + (' [' + platform + ']' if platform else '')
        pid = it.get('id')
        # 优先使用 id 路由；若无 id，则使用返回的 url（若为直链）
        if pid:
            pic = it.get('pic') or it.get('picUrl') or it.get('cover') or it.get('image') or it.get('thumbnail') or it.get('thumb') or ''
            item = {'label': label, 'path': plugin.url_for('tunehub_play', source=platform or 'netease', id=pid, br='320k')}
            if pic:
                item['thumbnail'] = pic
                item['icon'] = pic
                item['fanart'] = pic
            items.append(item)
        else:
            url = it.get('url')
            if url:
                pic = it.get('pic') or it.get('picUrl') or it.get('cover') or it.get('image') or it.get('thumbnail') or it.get('thumb') or ''
                item = {'label': label, 'path': url, 'is_playable': True}
                if pic:
                    item['thumbnail'] = pic
                    item['icon'] = pic
                    item['fanart'] = pic
                items.append(item)

    if not items:
        xbmcgui.Dialog().notification('TuneHub', '未找到结果', xbmcgui.NOTIFICATION_INFO, 800, False)
    return items


@plugin.route('/tunehub_playlist/')
def tunehub_playlist():
    # 显示三个平台文件夹
    platforms = [
        {'source': 'netease', 'name': '网易云歌单'},
        {'source': 'qq', 'name': 'QQ音乐歌单'},
        {'source': 'kuwo', 'name': '酷我歌单'}
    ]
    items = []
    for platform in platforms:
        items.append({
            'label': platform['name'],
            'path': plugin.url_for('tunehub_playlist_platform', source=platform['source']),
            'is_playable': False,
        })
    return items

@plugin.route('/tunehub_playlist_platform/<source>/')
def tunehub_playlist_platform(source):
    keyboard = xbmc.Keyboard('', '请输入歌单 ID')
    keyboard.doModal()
    if not keyboard.isConfirmed():
        return
    pid = keyboard.getText().strip()
    if not pid:
        return

    resp = music.tunehub_playlist(source, pid)
    data = resp.get('data') if isinstance(resp, dict) else resp
    # data 可能为 dict 包含 tracks 或 list
    tracks = []
    if isinstance(data, dict):
        tracks = data.get('tracks') or data.get('list') or data.get('songs') or []
    elif isinstance(data, list):
        tracks = data

    items = []
    for t in tracks:
        name = t.get('name') or ''
        artist = t.get('artist') or t.get('artistName') or ''
        items.append({'label': name + (' - ' + artist if artist else ''), 'path': plugin.url_for('tunehub_play', source=source, id=t.get('id'), br='320k')})
    if not items:
        xbmcgui.Dialog().notification('TuneHub', '未找到歌单或歌单为空', xbmcgui.NOTIFICATION_INFO, 800, False)
    return items


@plugin.route('/tunehub_toplists/')
def tunehub_toplists():
    # 显示三个平台文件夹
    platforms = [
        {'source': 'netease', 'name': '网易云排行榜'},
        {'source': 'qq', 'name': 'QQ音乐排行榜'},
        {'source': 'kuwo', 'name': '酷我排行榜'}
    ]
    items = []
    for platform in platforms:
        items.append({
            'label': platform['name'],
            'path': plugin.url_for('tunehub_toplists_platform', source=platform['source']),
            'is_playable': False,
        })
    return items

@plugin.route('/tunehub_toplists_platform/<source>/')
def tunehub_toplists_platform(source):
    # 显示特定平台的排行榜
    resp = music.tunehub_toplists(source=source, type='toplists')
    data = resp.get('data') if isinstance(resp, dict) else resp
    # Debug: log raw resp summary to help diagnose platform/source issues
    try:
        xbmc.log("plugin.audio.music: tunehub_toplists_platform called with source=%s resp_type=%s resp_keys=%s" % (
            str(source), str(type(resp)), str(list(resp.keys()) if isinstance(resp, dict) else 'N/A')), xbmc.LOGDEBUG)
    except Exception:
        pass
    lists = []
    if isinstance(data, dict):
        # 兼容多种 TuneHub 返回格式：优先 `lists`/`data`，再尝试 `list`，最后回退到顶层 resp 的 `list`
        lists = data.get('lists') or data.get('data') or data.get('list') or (resp.get('list') if isinstance(resp, dict) else None) or []
    elif isinstance(data, list):
        lists = data

    items = []
    # 尝试从响应的 data 层读取通用 source（如 data.source='qq'）以便为没有单项 platform 的条目补全来源
    common_source = None
    try:
        if isinstance(data, dict):
            common_source = data.get('source')
        elif isinstance(resp, dict):
            common_source = resp.get('source')
    except Exception:
        common_source = None
    try:
        xbmc.log("plugin.audio.music: tunehub_toplists_platform common_source=%s (user_selected=%s)" % (str(common_source), str(source)), xbmc.LOGDEBUG)
    except Exception:
        pass

    for l in lists:
        title = l.get('name') or l.get('title') or l.get('playlistName') or ''
        pid = l.get('id')
        item_platform = l.get('platform')
        item_source_field = l.get('source')
        item_source = item_platform or item_source_field or common_source or source
        try:
            xbmc.log("plugin.audio.music: tunehub_toplists_platform item id=%s platform=%s source_field=%s resolved_source=%s" % (
                str(pid), str(item_platform), str(item_source_field), str(item_source)), xbmc.LOGDEBUG)
        except Exception:
            pass
        if pid:
            pic = l.get('pic') or l.get('picUrl') or l.get('cover') or ''
            item = {'label': title, 'path': plugin.url_for('tunehub_toplist', source=item_source, id=pid)}
            if pic:
                item['icon'] = pic
                item['thumbnail'] = pic
            items.append(item)
    if not items:
        xbmcgui.Dialog().notification('TuneHub', '未找到排行榜', xbmcgui.NOTIFICATION_INFO, 800, False)
    return items



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

    # 关键修复：不要使用 referrer
    return []



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
def tunehub_toplist(source , id):
    """
    展示 TuneHub 榜单歌曲列表：
    - 自动兼容多种返回结构
    - 支持更多字段（专辑、时长、封面、平台）
    - 有缓存、错误处理、日志
    - 更丰富的 UI（infoLabels）
    """
    cache_key = f"tunehub_toplist_{source}_{id}"
    cache_ttl = 3600  # 1 小时缓存

    # -------------------------
    # 1. 读取缓存
    # -------------------------
    cached = plugin.get_storage().get(cache_key)
    if cached and time.time() - cached["time"] < cache_ttl:
        plugin.log.debug(f"[TuneHub] 使用缓存 toplist {source}/{id}")
        return cached["items"]

    try:
        resp = music.tunehub_toplist(source, id)
    except Exception as e:
        plugin.log.debug(f"[TuneHub] API 调用失败: {e}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification("TuneHub", "排行榜加载失败", xbmcgui.NOTIFICATION_ERROR, 3000)
        return []

    # -------------------------
    # 2. 解析数据结构
    # -------------------------
    data = resp.get("data") if isinstance(resp, dict) else resp
    if isinstance(data, dict):
        tracks = data.get("tracks") or data.get("list") or data.get("data") or []
    elif isinstance(data, list):
        tracks = data
    else:
        tracks = []

    items = []

    # -------------------------
    # 3. 遍历歌曲
    # -------------------------
    for it in tracks:
        name = it.get("name") or it.get("title") or ""
        artist = it.get("artist") or it.get("artistName") or ""
        album = it.get("album") or it.get("albumName") or ""
        duration = it.get("duration") or it.get("dt") or 0
        platform = it.get("platform") or it.get("source") or source

        # 封面字段兼容
        pic = (
            it.get("pic") or it.get("picUrl") or it.get("cover") or
            it.get("image") or it.get("thumbnail") or it.get("thumb") or ""
        )

        label = f"{name} - {artist} [{platform}]"

        pid = it.get("id")
        url = it.get("url")

        # -------------------------
        # 4. 构建 item
        # -------------------------
        # if pid:
        #     path = plugin.url_for("tunehub_play", source=platform, id=pid, br="320k")
        #     is_playable = False
        # else:
        #     path = url
        #     is_playable = True
        # is_playable = True
        # path = url
        item = {
            "label": label,
            "path": url,
            "is_playable": True,
            "thumbnail": pic,
            "icon": pic,
            "fanart": pic,
            "info": {
                "title": name,
                "artist": artist,
                "album": album,
                "duration": duration // 1000 if duration > 1000 else duration,
                "genre": it.get("genre") or "",
                "year": it.get("year") or 0,
                "mediatype": "song",
            }
        }

        items.append(item)

    # -------------------------
    # 5. 无结果提示
    # -------------------------
    if not items:
        xbmcgui.Dialog().notification("TuneHub", "未找到结果", xbmcgui.NOTIFICATION_INFO, 2000)
        return []

    # -------------------------
    # 6. 写入缓存
    # -------------------------
    plugin.get_storage()[cache_key] = {"time": time.time(), "items": items}

    plugin.log.debug(f"[TuneHub] 成功加载 toplist {source}/{id}，共 {len(items)} 首")

    return items


@plugin.route('/tunehub_play/<source>/<id>/<br>/')
def tunehub_play(source, id, br='320k'):
    try:
        resp = music.tunehub_url(id, br=br, source=source)
    except Exception:
        resp = {}

    url = None
    if isinstance(resp, dict):
        url = resp.get("url") or (resp.get("data") or {}).get("url")
    elif isinstance(resp, str):
        url = resp

    if not url:
        xbmcgui.Dialog().notification("TuneHub", "无法获取播放地址", xbmcgui.NOTIFICATION_INFO, 2000)
        return []

    # 获取元数据
    title = None
    artist = None
    album = None
    pic = None

    try:
        info_resp = music.tunehub_info(source, id)
        data = info_resp.get("data") if isinstance(info_resp, dict) else info_resp
        if isinstance(data, dict):
            title = data.get("name") or data.get("title")
            artist = data.get("artist") or data.get("artistName")
            album = data.get("album") or data.get("albumName")
            pic = data.get("pic") or data.get("picUrl") or data.get("cover")
    except:
        pass

    # 返回可播放媒体项（关键）
    return [{
        "label": title or "",
        "path": url,
        "is_playable": True,
        "thumbnail": pic,
        "icon": pic,
        "fanart": pic,
        "info": {
            "title": title,
            "artist": artist,
            "album": album,
            "mediatype": "song"
        }
    }]







@plugin.route('/recommend_playlists/')
def recommend_playlists():
    return get_playlists_items(music.recommend_resource().get("recommend", []))


@plugin.route('/hot_playlists/<offset>/')
def hot_playlists(offset):
    offset = int(offset)
    result = music.hot_playlists(offset=offset, limit=limit)
    playlists = result.get('playlists', [])
    items = get_playlists_items(playlists)
    if len(playlists) >= limit:
        items.append({'label': tag('下一页', 'yellow'), 'path': plugin.url_for(
            'hot_playlists', offset=str(offset+limit))})
    return items


@plugin.route('/user_playlists/<uid>/')
def user_playlists(uid):
    return get_playlists_items(music.user_playlist(uid).get("playlist", []))


@plugin.route('/playlist/<ptype>/<id>/')
def playlist(ptype, id):
    resp = music.playlist_detail(id)
    # return get_songs_items([song['id'] for song in songs],sourceId=id)
    if ptype == 'video':
        datas = resp.get('playlist', {}).get('videos', [])
        items = []
        for data in datas:

            label = data['mlogBaseData']['text']
            if 'song' in data['mlogExtVO']:
                artist = ", ".join([a["artistName"]
                                   for a in data['mlogExtVO']['song']['artists']])
                label += tag(' (' + artist + '-' +
                             data['mlogExtVO']['song']['name'] + ')', 'gray')
                context_menu = [
                    ('相关歌曲:%s' % (artist + '-' + data['mlogExtVO']['song']['name']), 'RunPlugin(%s)' % plugin.url_for('song_contextmenu', action='play_song', meida_type='song', song_id=str(
                        data['mlogExtVO']['song']['id']), mv_id=str(data['mlogBaseData']['id']), sourceId=str(id), dt=str(data['mlogExtVO']['song']['duration']//1000))),
                ]
            else:
                context_menu = []

            if data['mlogBaseData']['type'] == 2:
                # https://interface3.music.163.com/eapi/mlog/video/url
                meida_type = 'mlog'
            elif data['mlogBaseData']['type'] == 3:
                label = tag('[MV]') + label
                meida_type = 'mv'
            else:
                meida_type = ''

            items.append({
                'label': label,
                'path': plugin.url_for('play', meida_type=meida_type, song_id=str(data['mlogExtVO']['song']['id']), mv_id=str(data['mlogBaseData']['id']), sourceId=str(id), dt='0'),
                'is_playable': True,
                'icon': data['mlogBaseData']['coverUrl'],
                'thumbnail': data['mlogBaseData']['coverUrl'],
                'context_menu': context_menu,
                'info': {
                    'mediatype': 'video',
                    'title': data['mlogBaseData']['text'],
                },
                'info_type': 'video',
            })
        return items
    else:
        datas = resp.get('playlist', {}).get('tracks', [])
        privileges = resp.get('privileges', [])
        trackIds = resp.get('playlist', {}).get('trackIds', [])

        songs_number = len(trackIds)
        # 歌单中超过1000首歌
        if songs_number > len(datas):
            ids = [song['id'] for song in trackIds]
            resp2 = music.songs_detail(ids[len(datas):])
            datas.extend(resp2.get('songs', []))
            privileges.extend(resp2.get('privileges', []))
        return get_songs_items(datas, privileges=privileges, sourceId=id, source='playlist')


@plugin.route('/cloud/<offset>/')
def cloud(offset):
    offset = int(offset)
    result = music.cloud_songlist(offset=offset, limit=limit)
    more = result['hasMore']
    playlist = result['data']
    items = get_songs_items(playlist, offset=offset)
    if more:
        items.append({'label': tag('下一页', 'yellow'), 'path': plugin.url_for(
            'cloud', offset=str(offset+limit))})
    return items


if __name__ == '__main__':
    plugin.run()
