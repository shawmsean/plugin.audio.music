# 多音源搜索回退优化说明

## 概述

已优化搜索回退功能，改为按照指定顺序（kuwo, tencent, migu, kugou, netease）逐个尝试不同的音源，而不是只使用原来的音源。

## 主要改进

### 1. 多音源搜索回退

#### 改进前

```
原始音源: netease
    ↓
搜索 API: ?source=netease&name=晴天 周杰伦
    ↓
LXMUSIC API: /lxmusicv4/url/wy/new_id/master?sign=xxx
    ↓
如果失败 → 回退到 TuneHub/网易云
```

**问题**：
- 只尝试原始音源
- 如果原始音源没有这首歌，就无法获取播放链接
- 成功率较低

#### 改进后

```
原始音源: netease
    ↓
尝试音源 1: kuwo
    ↓
搜索 API: ?source=kuwo&name=晴天 周杰伦
    ↓
LXMUSIC API: /lxmusicv4/url/kw/new_id/master?sign=xxx
    ↓
如果失败 → 尝试下一个音源
    ↓
尝试音源 2: tencent
    ↓
搜索 API: ?source=tencent&name=晴天 周杰伦
    ↓
LXMUSIC API: /lxmusicv4/url/tx/new_id/master?sign=xxx
    ↓
如果失败 → 尝试下一个音源
    ↓
尝试音源 3: migu
    ↓
尝试音源 4: kugou
    ↓
尝试音源 5: netease
    ↓
所有音源都失败 → 回退到 TuneHub/网易云
```

**优势**：
- 尝试多个音源，成功率更高
- 某个音源没有这首歌时，可以尝试其他音源
- 不依赖单一音源的可用性

### 2. 音源顺序

按照以下顺序尝试（从最稳定的到最不稳定的）：

1. **kuwo** (酷我音乐)
   - 资源丰富
   - 稳定性高
   - 支持多种音质

2. **tencent** (腾讯音乐)
   - 资源丰富
   - 稳定性高
   - 支持多种音质

3. **migu** (咪咕音乐)
   - 无损资源多
   - 稳定性较高
   - 官方音源

4. **kugou** (酷狗音乐)
   - 资源丰富
   - 稳定性一般
   - 支持多种音质

5. **netease** (网易云音乐)
   - 资源丰富
   - 稳定性一般
   - 最后尝试

### 3. 详细日志输出

每个音源的尝试过程都有详细日志：

```
plugin.audio.music: 开始搜索回退: song_id=186122, song_name=晴天, artist=周杰伦, 原始源=wy
plugin.audio.music: 尝试音源: kuwo -> kw
plugin.audio.music: 音源 kuwo 找到 3 首歌曲
plugin.audio.music: 尝试搜索结果: id=123456, name=晴天, artist=周杰伦
plugin.audio.music: LXMUSIC 请求 URL: https://88.lxmusic.xn--fiqs8s/lxmusicv4/url/kw/123456/master?sign=...
plugin.audio.music: LXMUSIC 获取播放链接成功: https://...
plugin.audio.music: URL检查 https://... 状态码: 200
plugin.audio.music: 搜索回退成功: 原ID=186122 -> 新ID=123456, 音源=kuwo, URL=https://...
```

如果第一个音源失败：

```
plugin.audio.music: 音源 kuwo 未找到搜索结果
plugin.audio.music: 尝试音源: tencent -> tx
plugin.audio.music: 音源 tencent 找到 2 首歌曲
plugin.audio.music: 尝试搜索结果: id=789012, name=晴天, artist=周杰伦
plugin.audio.music: LXMUSIC 响应数据: {'code': 2, 'msg': 'failed'}
plugin.audio.music: 音源 tencent 所有搜索结果均失败，尝试下一个音源
plugin.audio.music: 尝试音源: migu -> mg
...
```

## 数据流示例

### 场景 1: 第一个音源成功

```
请求: songs_url_v1(ids=['186122'], level='jymaster', source='netease')
    ↓
LXMUSIC API (wy) → code: 2 (失败)
    ↓
TuneHub API → 502 (失败)
    ↓
触发搜索回退
    ↓
网易云 API → 获取歌曲信息: name='晴天', artist='周杰伦'
    ↓
尝试音源 1: kuwo
    ↓
搜索 API: ?source=kuwo&name=晴天 周杰伦
    ↓
找到 3 首歌曲
    ↓
尝试第 1 首歌: id=123456, name=晴天, artist=周杰伦
    ↓
LXMUSIC API (kw) → https://music.example.com/kw/123456.flac
    ↓
URL 检查 → 200 OK
    ↓
返回: {'data': [{'id': '186122', 'url': 'https://...', 'source': 'lxmusic_search_after_tunehub'}]}
```

### 场景 2: 前几个音源失败，最后一个成功

```
请求: songs_url_v1(ids=['186122'], level='jymaster', source='netease')
    ↓
LXMUSIC API (wy) → 失败
    ↓
TuneHub API → 失败
    ↓
触发搜索回退
    ↓
尝试音源 1: kuwo → 未找到结果
    ↓
尝试音源 2: tencent → 找到但链接不可用
    ↓
尝试音源 3: migu → 找到但链接不可用
    ↓
尝试音源 4: kugou → 找到但链接不可用
    ↓
尝试音源 5: netease → 找到且链接可用
    ↓
返回: {'data': [{'id': '186122', 'url': 'https://...', 'source': 'lxmusic_search_after_tunehub'}]}
```

### 场景 3: 所有音源都失败

```
请求: songs_url_v1(ids=['186122'], level='jymaster', source='netease')
    ↓
LXMUSIC API (wy) → 失败
    ↓
TuneHub API → 失败
    ↓
触发搜索回退
    ↓
尝试音源 1: kuwo → 未找到结果
    ↓
尝试音源 2: tencent → 未找到结果
    ↓
尝试音源 3: migu → 未找到结果
    ↓
尝试音源 4: kugou → 未找到结果
    ↓
尝试音源 5: netease → 未找到结果
    ↓
搜索回退所有音源均失败
    ↓
回退到网易云原始接口
    ↓
返回: {'data': [{'id': '186122', 'url': 'https://...', 'source': 'netease'}]}
```

## 代码实现

### 音源顺序定义

```python
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
```

### 搜索回退流程

```python
# 按照顺序尝试每个音源
for search_source in search_sources_order:
    lxmusic_source = source_mapping.get(search_source)
    
    # 在当前音源中搜索歌曲
    search_results = self._search_music_by_name(keyword, search_source, limit=3)
    
    # 尝试每个搜索结果
    for song in search_results:
        new_song_id = song.get('id')
        
        # 使用新的歌曲 ID 调用 LXMUSIC API
        new_url = self._lxmusic_get_music_url(lxmusic_source, new_song_id, quality)
        
        if new_url and self._check_url_valid(new_url):
            return new_url
    
    # 如果当前音源的所有搜索结果都失败，尝试下一个音源
    continue
```

## 优势总结

### 1. **更高的成功率**

- 尝试 5 个不同的音源
- 某个音源没有这首歌时，可以尝试其他音源
- 不依赖单一音源的可用性

### 2. **更好的容错性**

- 单个音源故障不影响整体功能
- 音源资源差异不影响播放
- 网络问题导致的单个音源不可用可以绕过

### 3. **更智能的资源利用**

- 优先使用资源丰富的音源（kuwo/tencent）
- 自动选择可用的音源
- 避免使用不稳定的音源

### 4. **详细的日志输出**

- 记录每个音源的尝试过程
- 记录每个搜索结果的验证过程
- 便于问题排查和优化

## 注意事项

### 1. 性能考虑

- 多音源搜索会增加 API 调用次数
- 最多可能调用 5 个搜索 API + 5 个 LXMUSIC API
- 建议添加缓存机制减少重复调用

### 2. 搜索准确性

- 不同音源可能有不同的歌曲 ID
- 搜索结果可能不完全匹配
- 建议添加智能匹配算法

### 3. 版权限制

- 不同音源的版权范围不同
- 某些歌曲可能在某些音源中不可用
- 需要尊重各音源的版权政策

## 测试建议

### 测试用例

```python
# 测试 1: 第一个音源成功
result = netease.songs_url_v1(
    ids=['186122'],
    level='jymaster',
    source='netease'
)

# 测试 2: 前几个音源失败，最后一个成功
result = netease.songs_url_v1(
    ids=['186122'],
    level='jymaster',
    source='netease'
)

# 测试 3: 所有音源都失败
result = netease.songs_url_v1(
    ids=['invalid_id'],
    level='jymaster',
    source='netease'
)
```

### 验证要点

1. ✅ 按照指定顺序尝试音源
2. ✅ 每个音源都尝试多个搜索结果
3. ✅ URL 可用性检查
4. ✅ 日志输出完整准确
5. ✅ 返回结果的 `source` 字段正确
6. ✅ 失败时能正确回退到下一个音源

## 后续优化建议

### 1. 添加音源成功率统计

```python
source_success_rate = {
    'kuwo': 0,
    'tencent': 0,
    'migu': 0,
    'kugou': 0,
    'netease': 0
}
```

### 2. 动态调整音源顺序

```python
# 根据成功率动态调整音源顺序
sorted_sources = sorted(source_success_rate.items(), key=lambda x: x[1], reverse=True)
search_sources_order = [source for source, _ in sorted_sources]
```

### 3. 添加智能匹配算法

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

### 4. 添加缓存机制

```python
@functools.lru_cache(maxsize=1000)
def _search_music_by_name_cached(self, keyword, source, limit):
    return self._search_music_by_name(keyword, source, limit)
```

## 更新日志

### 2026-01-29

- ✅ 实现多音源搜索回退
- ✅ 按照指定顺序尝试音源（kuwo, tencent, migu, kugou, netease）
- ✅ 每个音源尝试多个搜索结果
- ✅ 添加详细的日志输出
- ✅ 优化错误处理

## 联系方式

如有问题，请提交 GitHub Issue。

---

**最后更新**: 2026-01-29
**API 版本**: v2.2
**插件版本**: v2.3.0
