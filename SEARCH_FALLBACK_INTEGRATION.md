# 智能搜索回退集成说明

## 概述

已成功为 `songs_url_v1` 方法添加智能搜索回退功能，当 LXMUSIC API 返回的链接不可用时，自动使用搜索 API 获取新的歌曲 ID，然后重新调用 LXMUSIC API。

## 新增功能

### 1. 搜索 API 集成

**搜索 API**: `https://music-api.gdstudio.xyz/api.php`

**支持的音源**:
- kuwo (酷我音乐)
- netease (网易云音乐)
- tencent (腾讯音乐)
- migu (咪咕音乐)
- kugou (酷狗音乐)

### 2. 新增方法

#### `_search_music_by_name(keyword, source='kuwo', limit=5)`

通过搜索 API 搜索音乐：

```python
result = self._search_music_by_name('晴天 周杰伦', 'netease', limit=5)
# 返回: [{'id': '123456', 'name': '晴天', 'artist': '周杰伦', 'album': '叶惠美', 'source': 'netease'}, ...]
```

#### `_check_url_valid(url)`

检查 URL 是否可用（通过 HEAD 请求）：

```python
is_valid = self._check_url_valid('https://example.com/music.mp3')
# 返回: True/False
```

#### `_search_and_retry_lxmusic(song_id, song_name, artist_name, target_source, quality)`

通过搜索 API 获取新的歌曲 ID，然后重新调用 LXMUSIC API：

```python
url = self._search_and_retry_lxmusic('123456', '晴天', '周杰伦', 'wy', 'flac')
# 返回: 'https://...'
```

### 3. 优化 `songs_url_v1` 方法

#### 新增参数

```python
def songs_url_v1(self, ids, level, source='netease', song_names=None, artist_names=None):
    """
    Args:
        ids: 歌曲ID列表
        level: 音质级别
        source: 音源
        song_names: 歌曲名称列表（用于搜索回退）
        artist_names: 歌手名称列表（用于搜索回退）
    """
```

#### 新的播放链接获取策略

```
对于支持搜索回退的音源（wy/tx/mg/kg/kw）：

1. 尝试 LXMUSIC API
   ↓ (获取到链接)
2. 检查链接是否可用
   ↓ (不可用)
3. 使用搜索 API 搜索歌曲（song_name + artist_name）
   ↓ (找到搜索结果)
4. 使用新的歌曲 ID 调用 LXMUSIC API
   ↓ (获取到新链接)
5. 检查新链接是否可用
   ↓ (可用)
6. 返回新链接
   ↓ (不可用或找不到)
7. 回退到 TuneHub
   ↓ (失败)
8. 回退到网易云
```

## 使用示例

### 基本用法

```python
from api import NetEase

netease = NetEase()

# 获取播放链接（带搜索回退）
result = netease.songs_url_v1(
    ids=['123456', '789012'],
    level='lossless',
    source='tencent',
    song_names=['晴天', '告白气球'],
    artist_names=['周杰伦', '周杰伦']
)

# 解析结果
for item in result['data']:
    print(f"歌曲ID: {item['id']}")
    print(f"播放链接: {item['url']}")
    print(f"音质: {item['level']}")
    print(f"来源: {item['source']}")  # lxmusic/lxmusic_search/tunehub/netease
```

### 单个歌曲

```python
result = netease.songs_url_v1(
    ids='123456',
    level='lossless',
    source='tencent',
    song_names='晴天',
    artist_names='周杰伦'
)
```

### 不提供搜索信息（回退到原有逻辑）

```python
result = netease.songs_url_v1(
    ids=['123456'],
    level='lossless',
    source='tencent'
    # 不提供 song_names 和 artist_names，搜索回退不会触发
)
```

## 数据流示例

### 场景 1: LXMUSIC 链接可用

```
请求: songs_url_v1(ids=['123456'], level='lossless', source='tencent', song_names=['晴天'], artist_names=['周杰伦'])
    ↓
LXMUSIC API: /lxmusicv4/url/tx/123456/flac?sign=xxx
    ↓
返回链接: https://music.example.com/tencent/123456.flac
    ↓
URL 检查: HEAD 请求 → 200 OK
    ↓
返回结果: {'data': [{'id': '123456', 'url': 'https://...', 'level': 'lossless', 'source': 'lxmusic'}]}
```

### 场景 2: LXMUSIC 链接不可用，搜索回退成功

```
请求: songs_url_v1(ids=['123456'], level='lossless', source='tencent', song_names=['晴天'], artist_names=['周杰伦'])
    ↓
LXMUSIC API: /lxmusicv4/url/tx/123456/flac?sign=xxx
    ↓
返回链接: https://expired.example.com/tencent/123456.flac
    ↓
URL 检查: HEAD 请求 → 404 Not Found
    ↓
触发搜索回退: keyword='晴天 周杰伦', source='tencent'
    ↓
搜索 API: ?types=search&source=tencent&name=晴天 周杰伦
    ↓
搜索结果: [{'id': '789012', 'name': '晴天', 'artist': '周杰伦'}, ...]
    ↓
尝试新ID: 789012
    ↓
LXMUSIC API: /lxmusicv4/url/tx/789012/flac?sign=xxx
    ↓
返回新链接: https://music.example.com/tencent/789012.flac
    ↓
URL 检查: HEAD 请求 → 200 OK
    ↓
返回结果: {'data': [{'id': '123456', 'url': 'https://...', 'level': 'lossless', 'source': 'lxmusic_search'}]}
```

### 场景 3: 搜索回退失败，回退到 TuneHub

```
请求: songs_url_v1(ids=['123456'], level='lossless', source='tencent', song_names=['晴天'], artist_names=['周杰伦'])
    ↓
LXMUSIC API → 链接不可用
    ↓
搜索回退 → 未找到结果或链接不可用
    ↓
TuneHub API: ?source=tencent&id=123456&type=url
    ↓
返回链接: https://music.example.com/tencent/123456.flac
    ↓
URL 检查: HEAD 请求 → 200 OK
    ↓
返回结果: {'data': [{'id': '123456', 'url': 'https://...', 'level': 'lossless', 'source': 'tunehub'}]}
```

## 日志输出示例

### 成功获取播放链接（LXMUSIC）

```
plugin.audio.music: songs_url_v1 ids_list=['123456'] level=lossless source=tencent
plugin.audio.music: LXMUSIC source mapping: tencent -> tx, quality: lossless -> flac
plugin.audio.music: songs_url_v1 trying LXMUSIC id=123456 source=tx
plugin.audio.music: LXMUSIC 请求 URL: https://88.lxmusic.xn--fiqs8s/lxmusicv4/url/tx/123456/flac?sign=...
plugin.audio.music: LXMUSIC 响应数据: {'code': 0, 'data': 'https://...'}
plugin.audio.music: LXMUSIC 获取播放链接成功: https://...
plugin.audio.music: URL检查 https://... 状态码: 200
plugin.audio.music: songs_url_v1 LXMUSIC success id=123456 url=https://...
plugin.audio.music: songs_url_v1 id=123456 url=https://... used_source=lxmusic
```

### 搜索回退成功

```
plugin.audio.music: songs_url_v1 LXMUSIC URL不可用 id=123456
plugin.audio.music: songs_url_v1 尝试搜索回退 id=123456 song_name=晴天 artist_name=周杰伦
plugin.audio.music: 开始搜索回退: song_id=123456, song_name=晴天, artist=周杰伦, source=tencent
plugin.audio.music: 搜索API请求: keyword=晴天 周杰伦, source=tencent
plugin.audio.music: 搜索API找到 3 首歌曲
plugin.audio.music: 尝试搜索结果: id=789012, name=晴天, artist=周杰伦
plugin.audio.music: LXMUSIC 请求 URL: https://88.lxmusic.xn--fiqs8s/lxmusicv4/url/tx/789012/flac?sign=...
plugin.audio.music: LXMUSIC 获取播放链接成功: https://...
plugin.audio.music: URL检查 https://... 状态码: 200
plugin.audio.music: 搜索回退成功: 原ID=123456 -> 新ID=789012, URL=https://...
plugin.audio.music: songs_url_v1 id=123456 url=https://... used_source=lxmusic_search
```

### 搜索回退失败

```
plugin.audio.music: songs_url_v1 LXMUSIC URL不可用 id=123456
plugin.audio.music: songs_url_v1 尝试搜索回退 id=123456 song_name=晴天 artist_name=周杰伦
plugin.audio.music: 搜索API请求: keyword=晴天 周杰伦, source=tencent
plugin.audio.music: 搜索API未找到结果: 晴天 周杰伦
plugin.audio.music: 搜索回退未找到结果: 晴天 周杰伦
plugin.audio.music: songs_url_v1 trying TuneHub id=123456
plugin.audio.music: songs_url_v1 TuneHub success id=123456 url=https://...
```

## 支持的音源

| LXMUSIC 标识符 | 搜索 API 音源 | 搜索回退支持 | 说明 |
|----------------|--------------|-------------|------|
| wy | netease | ✅ | 网易云音乐 |
| tx | tencent | ✅ | 腾讯音乐 |
| mg | migu | ✅ | 咪咕音乐 |
| kg | kugou | ✅ | 酷狗音乐 |
| kw | kuwo | ✅ | 酷我音乐 |
| jm | - | ❌ | JOOX 音乐 |
| dp | - | ❌ | Deezer |
| xm | - | ❌ | 喜马拉雅 |
| ap | - | ❌ | Apple Music |
| sp | - | ❌ | Spotify |
| yt | - | ❌ | YouTube Music |
| qd | - | ❌ | Qobuz |
| td | - | ❌ | Tidal |

## 性能优化

### 1. URL 检查优化

- 使用 HEAD 请求而不是 GET 请求，减少数据传输
- 超时时间设置为 5 秒，避免长时间等待
- 只在必要时检查 URL（LXMUSIC 和 TuneHub 返回后）

### 2. 搜索回退限制

- 最多尝试 3 个搜索结果
- 搜索结果限制为 5 首
- 只在提供歌曲名称或歌手名称时触发

### 3. 缓存建议（可选）

```python
# 可以添加 URL 检查结果缓存
from functools import lru_cache

@lru_cache(maxsize=1000)
def _check_url_valid_cached(self, url):
    return self._check_url_valid(url)
```

## 错误处理

### 1. LXMUSIC 错误

| 错误 | 处理方式 |
|------|----------|
| API 请求失败 | 回退到 TuneHub |
| 返回空链接 | 触发搜索回退（如果提供搜索信息） |
| 链接不可用 | 触发搜索回退（如果提供搜索信息） |
| 429 限流 | 使用指数退避重试 |

### 2. 搜索 API 错误

| 错误 | 处理方式 |
|------|----------|
| API 请求失败 | 回退到 TuneHub |
| 未找到结果 | 回退到 TuneHub |
| 找到结果但链接不可用 | 尝试下一个结果 |
| 所有结果都失败 | 回退到 TuneHub |

### 3. URL 检查错误

| 错误 | 处理方式 |
|------|----------|
| 请求超时 | 认为链接不可用 |
| 网络错误 | 认为链接不可用 |
| 4xx/5xx 状态码 | 认为链接不可用 |
| 200 状态码 | 认为链接可用 |

## 注意事项

### 1. 性能考虑

- URL 检查会额外增加请求时间（每个 URL 约 5 秒）
- 搜索回退会增加额外的 API 调用
- 建议在批量请求时使用并发处理

### 2. 搜索信息准确性

- 搜索回退依赖于歌曲名称和歌手名称的准确性
- 如果搜索信息不准确，可能找不到正确的歌曲
- 建议在调用前确保搜索信息的准确性

### 3. 音源限制

- 只有 5 个音源支持搜索回退（wy/tx/mg/kg/kw）
- 其他音源（jm/dp/xm/ap/sp/yt/qd/td）不会触发搜索回退
- 如果使用这些音源，会直接回退到 TuneHub

### 4. 版权声明

- 本功能仅供学习研究使用
- 请勿用于商业用途
- 请支持正版音乐

## 测试建议

### 测试用例

```python
# 测试 1: LXMUSIC 链接可用
result = netease.songs_url_v1(
    ids=['123456'],
    level='lossless',
    source='tencent',
    song_names=['晴天'],
    artist_names=['周杰伦']
)

# 测试 2: LXMUSIC 链接不可用，搜索回退成功
# (需要使用一个已失效的歌曲 ID)

# 测试 3: 搜索回退失败，TuneHub 成功
# (需要使用一个搜索不到的歌曲)

# 测试 4: 不提供搜索信息
result = netease.songs_url_v1(
    ids=['123456'],
    level='lossless',
    source='tencent'
    # 不会触发搜索回退
)

# 测试 5: 批量请求
result = netease.songs_url_v1(
    ids=['123456', '789012', '345678'],
    level='lossless',
    source='tencent',
    song_names=['晴天', '告白气球', '七里香'],
    artist_names=['周杰伦', '周杰伦', '周杰伦']
)
```

### 验证要点

1. ✅ LXMUSIC 链接可用时直接返回
2. ✅ LXMUSIC 链接不可用且提供搜索信息时触发搜索回退
3. ✅ 搜索回退能找到正确的歌曲并获取可用链接
4. ✅ 搜索回退失败时能正确回退到 TuneHub
5. ✅ 不提供搜索信息时不会触发搜索回退
6. ✅ 不支持搜索回退的音源能正常工作
7. ✅ 日志输出完整准确

## 后续优化建议

### 1. 添加 URL 检查缓存

```python
@functools.lru_cache(maxsize=1000)
def _check_url_valid_cached(self, url):
    return self._check_url_valid(url)
```

### 2. 添加搜索结果缓存

```python
@functools.lru_cache(maxsize=500)
def _search_music_by_name_cached(self, keyword, source, limit):
    return self._search_music_by_name(keyword, source, limit)
```

### 3. 实现并发处理

```python
from concurrent.futures import ThreadPoolExecutor

def _get_urls_concurrent(self, ids_list, song_names, artist_names, source, level):
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for idx, _id in enumerate(ids_list):
            future = executor.submit(
                self._get_single_url_with_fallback,
                _id,
                song_names[idx] if idx < len(song_names) else None,
                artist_names[idx] if idx < len(artist_names) else None,
                source,
                level
            )
            futures.append(future)
        return [f.result() for f in futures]
```

### 4. 添加智能匹配

```python
def _match_best_song(self, search_results, song_name, artist_name):
    """从搜索结果中找到最匹配的歌曲"""
    best_match = None
    best_score = 0

    for song in search_results:
        score = 0
        if song_name and song_name in song.get('name', ''):
            score += 50
        if artist_name and artist_name in song.get('artist', ''):
            score += 50

        if score > best_score:
            best_score = score
            best_match = song

    return best_match
```

## 更新日志

### 2026-01-29

- ✅ 集成搜索 API
- ✅ 添加 URL 检查功能
- ✅ 实现智能搜索回退
- ✅ 优化 `songs_url_v1` 方法
- ✅ 添加详细日志
- ✅ 完善错误处理

## 联系方式

如有问题，请提交 GitHub Issue。

---

**最后更新**: 2026-01-29
**API 版本**: v2.0
**插件版本**: v2.1.0
