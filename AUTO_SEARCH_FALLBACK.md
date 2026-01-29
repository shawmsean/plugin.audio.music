# 自动搜索回退功能优化说明

## 问题分析

从日志中发现的问题：

```
plugin.audio.music: songs_url_v1 ids_list=['186122'] level=jymaster source=netease
plugin.audio.music: LXMUSIC source mapping: netease -> wy, quality: jymaster -> master
plugin.audio.music: songs_url_v1 trying LXMUSIC id=186122 source=wy
plugin.audio.music: LXMUSIC 响应数据: {'code': 2, 'msg': 'failed', 'data': None}
plugin.audio.music: songs_url_v1 LXMUSIC failed id=186122 error=LXMUSIC 错误: failed
plugin.audio.music: songs_url_v1 trying TuneHub id=186122
plugin.audio.music: tunehub_request HTTP error status=502, returning None for fallback
plugin.audio.music: songs_url_v1 id=186122 url=None used_source=None
plugin.audio.music: songs_url_v1 missing_ids after LXMUSIC/TuneHub: ['186122']
plugin.audio.music: songs_url_v1 falling back to NetEase ids=['186122']
```

### 问题根源

1. **LXMUSIC 失败**：返回 `code: 2`，表示获取播放链接失败
2. **TuneHub 失败**：返回 502 错误
3. **没有触发搜索回退**：直接回退到网易云原始接口
4. **原因**：调用时没有提供 `song_names` 和 `artist_names` 参数，搜索回退的触发条件不满足

## 解决方案

### 1. 新增 `_get_song_info_from_netease` 方法

从网易云自动获取歌曲信息（歌曲名和歌手名），用于搜索回退：

```python
def _get_song_info_from_netease(self, song_id: str) -> dict:
    """
    从网易云获取歌曲信息（用于搜索回退）

    Returns:
        {'name': song_name, 'artist': artist_name}
    """
    try:
        # 调用网易云 songs_detail API
        data = self.songs_detail([song_id])

        if data and 'songs' in data and len(data['songs']) > 0:
            song = data['songs'][0]
            song_name = song.get('name', '')
            artist_list = song.get('ar', [])
            artist_name = ', '.join([ar.get('name', '') for ar in artist_list])

            return {'name': song_name, 'artist': artist_name}
        return {}
    except Exception as e:
        return {}
```

### 2. 增强 `_search_and_retry_lxmusic` 方法

在搜索回退时，如果没有提供歌曲信息，自动从网易云获取：

```python
def _search_and_retry_lxmusic(self, song_id: str, song_name: str, artist_name: str,
                              target_source: str, quality: str) -> str:
    # ... 原有代码 ...

    # 如果没有提供歌曲名称或歌手名称，尝试从网易云获取
    if not song_name and not artist_name:
        xbmc.log("plugin.audio.music: 未提供歌曲信息，尝试从网易云获取", xbmc.LOGDEBUG)
        song_info = self._get_song_info_from_netease(song_id)
        if song_info:
            song_name = song_info.get('name', '')
            artist_name = song_info.get('artist', '')
            xbmc.log("plugin.audio.music: 从网易云获取到歌曲信息: name={}, artist={}".format(
                song_name, artist_name), xbmc.LOGDEBUG)

    # 如果仍然没有歌曲信息，无法进行搜索回退
    if not song_name and not artist_name:
        xbmc.log("plugin.audio.music: 无法获取歌曲信息，跳过搜索回退", xbmc.LOGWARNING)
        return ''

    # ... 继续搜索回退逻辑 ...
```

### 3. 优化 `songs_url_v1` 方法

在 TuneHub 失败后，也尝试搜索回退：

```python
# 2. 如果 LXMUSIC 失败或 source 是 netease，尝试 TuneHub
if not url:
    try:
        # ... TuneHub 逻辑 ...
    except Exception as e:
        url = None

# 2.5. 如果 TuneHub 也失败，且支持搜索回退，尝试搜索回退
if not url and lxmusic_source:
    xbmc.log("plugin.audio.music: songs_url_v1 TuneHub失败，尝试搜索回退 id={}".format(_id), xbmc.LOGDEBUG)
    url = self._search_and_retry_lxmusic(str(_id), song_name, artist_name, lxmusic_source, quality)
    if url:
        used_source = 'lxmusic_search_after_tunehub'
```

## 新的播放链接获取策略

```
对于支持搜索回退的音源（wy/tx/mg/kg/kw）：

1. 尝试 LXMUSIC API
   ↓ (失败)
2. 检查是否提供 song_names/artist_names
   ↓ (未提供)
3. 从网易云获取歌曲信息
   ↓ (成功)
4. 使用搜索 API 搜索歌曲
   ↓ (找到)
5. 使用新歌曲 ID 调用 LXMUSIC API
   ↓ (成功)
6. 返回播放链接
   ↓ (失败)
7. 尝试 TuneHub API
   ↓ (失败)
8. 再次尝试搜索回退（使用从网易云获取的歌曲信息）
   ↓ (失败)
9. 回退到网易云原始接口
```

## 数据流示例

### 场景 1: 未提供歌曲信息，LXMUSIC 失败，搜索回退成功

```
请求: songs_url_v1(ids=['186122'], level='jymaster', source='netease')
    ↓
LXMUSIC API → code: 2 (失败)
    ↓
TuneHub API → 502 错误 (失败)
    ↓
触发搜索回退（自动获取歌曲信息）
    ↓
网易云 API → songs_detail(['186122'])
    ↓
获取歌曲信息: name='晴天', artist='周杰伦'
    ↓
搜索 API: ?source=netease&name=晴天 周杰伦
    ↓
搜索结果: [{'id': '789012', 'name': '晴天', 'artist': '周杰伦'}]
    ↓
LXMUSIC API（新ID: 789012）→ https://...
    ↓
URL 检查 → 200 OK
    ↓
返回结果: {'data': [{'id': '186122', 'url': 'https://...', 'source': 'lxmusic_search_after_tunehub'}]}
```

### 场景 2: 提供了歌曲信息，LXMUSIC 失败，搜索回退成功

```
请求: songs_url_v1(ids=['186122'], level='jymaster', source='netease', song_names=['晴天'], artist_names=['周杰伦'])
    ↓
LXMUSIC API → code: 2 (失败)
    ↓
触发搜索回退（直接使用提供的歌曲信息）
    ↓
搜索 API: ?source=netease&name=晴天 周杰伦
    ↓
搜索结果: [{'id': '789012', 'name': '晴天', 'artist': '周杰伦'}]
    ↓
LXMUSIC API（新ID: 789012）→ https://...
    ↓
返回结果: {'data': [{'id': '186122', 'url': 'https://...', 'source': 'lxmusic_search'}]}
```

### 场景 3: 所有尝试都失败，回退到网易云

```
请求: songs_url_v1(ids=['186122'], level='jymaster', source='netease')
    ↓
LXMUSIC API → code: 2 (失败)
    ↓
TuneHub API → 502 错误 (失败)
    ↓
搜索回退（自动获取歌曲信息）
    ↓
网易云 API → 获取歌曲信息成功
    ↓
搜索 API → 未找到结果
    ↓
网易云原始接口 → https://...
    ↓
返回结果: {'data': [{'id': '186122', 'url': 'https://...', 'source': 'netease'}]}
```

## 返回结果中的 `source` 字段

| 值 | 说明 |
|----|------|
| `lxmusic` | 直接从 LXMUSIC API 获取 |
| `lxmusic_search` | LXMUSIC 失败后，使用提供的歌曲信息进行搜索回退 |
| `lxmusic_search_after_tunehub` | LXMUSIC 和 TuneHub 都失败后，使用自动获取的歌曲信息进行搜索回退 |
| `tunehub` | 从 TuneHub API 获取 |
| `netease` | 从网易云原始接口获取 |

## 优势总结

### 1. **完全自动化**

- 无需手动提供歌曲信息
- 自动从网易云获取歌曲名和歌手名
- 自动触发搜索回退

### 2. **更高的成功率**

- 四级回退机制：LXMUSIC → 搜索回退 → TuneHub → 网易云
- 即使没有提供歌曲信息也能触发搜索回退
- 多次尝试确保总能获取到播放链接

### 3. **向后兼容**

- 提供歌曲信息时直接使用，不调用网易云 API
- 不提供歌曲信息时自动获取
- 不影响现有调用方式

### 4. **详细的日志**

每个步骤都有详细日志，便于问题排查：
- 是否从网易云获取歌曲信息
- 获取到的歌曲信息内容
- 搜索回退的触发时机
- 搜索回退的结果

## 性能影响

### 1. 额外的 API 调用

- **网易云 songs_detail API**：只在需要搜索回退且未提供歌曲信息时调用
- **搜索 API**：只在搜索回退时调用
- **LXMUSIC API（额外）**：搜索回退时会再次调用

### 2. 优化建议

可以添加歌曲信息缓存，减少重复调用：

```python
@functools.lru_cache(maxsize=1000)
def _get_song_info_cached(self, song_id: str) -> dict:
    return self._get_song_info_from_netease(song_id)
```

## 测试建议

### 测试用例

```python
# 测试 1: 未提供歌曲信息，LXMUSIC 失败，搜索回退成功
result = netease.songs_url_v1(
    ids=['186122'],
    level='jymaster',
    source='netease'
    # 不提供 song_names 和 artist_names
)

# 测试 2: 提供歌曲信息，LXMUSIC 失败，搜索回退成功
result = netease.songs_url_v1(
    ids=['186122'],
    level='jymaster',
    source='netease',
    song_names=['晴天'],
    artist_names=['周杰伦']
)

# 测试 3: 所有尝试都失败，回退到网易云
result = netease.songs_url_v1(
    ids=['invalid_id'],
    level='jymaster',
    source='netease'
)
```

### 验证要点

1. ✅ 未提供歌曲信息时能自动从网易云获取
2. ✅ LXMUSIC 失败后能触发搜索回退
3. ✅ TuneHub 失败后也能触发搜索回退
4. ✅ 搜索回退能找到正确的歌曲
5. ✅ 日志输出完整准确
6. ✅ 返回结果的 `source` 字段正确

## 注意事项

### 1. 网易云 API 限制

- `songs_detail` API 可能有限流
- 需要登录才能获取歌曲信息
- 建议添加错误处理和重试机制

### 2. 性能考虑

- 自动获取歌曲信息会增加额外的 API 调用
- 建议添加歌曲信息缓存
- 批量请求时可以考虑并发处理

### 3. 搜索准确性

- 从网易云获取的歌曲信息可能不准确
- 搜索结果可能不匹配
- 建议添加智能匹配算法

## 更新日志

### 2026-01-29

- ✅ 新增 `_get_song_info_from_netease` 方法
- ✅ 增强 `_search_and_retry_lxmusic` 方法
- ✅ 优化 `songs_url_v1` 方法
- ✅ 在 TuneHub 失败后也尝试搜索回退
- ✅ 支持自动获取歌曲信息
- ✅ 完善日志输出

## 联系方式

如有问题，请提交 GitHub Issue。

---

**最后更新**: 2026-01-29
**API 版本**: v2.1
**插件版本**: v2.2.0
