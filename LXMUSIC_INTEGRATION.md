# LXMUSIC API 集成说明

## 概述

已成功将 LXMUSIC 的播放链接解析逻辑集成到 `plugin.audio.music` 插件的 `songs_url_v1` 方法中。

## 集成内容

### 1. 新增常量配置

在 `api.py` 文件顶部添加了 LXMUSIC API 相关配置：

```python
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
```

### 2. 新增方法

#### `_lxmusic_sha256(message: str) -> str`
- SHA256 哈希函数
- 用于生成 API 请求签名

#### `_lxmusic_generate_sign(request_path: str) -> str`
- 生成 LXMUSIC API 请求签名
- 签名算法: `SHA256(requestPath + SCRIPT_MD5 + SECRET_KEY)`

#### `_lxmusic_make_request(url: str, timeout: int = 10) -> dict`
- 发送 LXMUSIC API HTTP 请求
- 处理响应解析和错误处理

#### `_lxmusic_get_music_url_single(source: str, songmid: str, quality: str, timeout: int = 10) -> str`
- 单次尝试获取音乐播放链接
- 构建请求、生成签名、发送请求、解析响应

#### `_lxmusic_get_music_url(source: str, songmid: str, quality: str, max_retries: int = 3, timeout: int = 10) -> str`
- 获取音乐播放链接（带重试机制）
- 支持指数退避策略
- 最多重试 3 次

#### `_convert_level_to_quality(level: str) -> str`
- 将网易云的 level 转换为 LXMUSIC 的 quality
- 支持的音质映射：
  - `standard` → `128k`
  - `exceed` → `320k`
  - `high` → `320k`
  - `lossless` → `flac`
  - `hires` → `flac24bit`
  - `dolby` → `atmos`
  - `jyeffect` → `flac`
  - `jymaster` → `master`

### 3. 修改 `songs_url_v1` 方法

#### 新的播放链接获取策略

```
1. 如果 source 支持且不是 netease，优先使用 LXMUSIC API
   ↓ (失败)
2. 尝试 TuneHub API
   ↓ (失败)
3. 回退到网易云原始接口
```

#### 优先级

1. **LXMUSIC API**（非 netease 音源）
   - 支持 12 个音乐平台
   - 稳定性高
   - 音质丰富

2. **TuneHub API**（所有音源）
   - 作为备用方案
   - 支持多种音源

3. **网易云原始接口**（netease 音源）
   - 作为最后的回退方案
   - 只在 LXMUSIC 和 TuneHub 都失败时使用

## 使用方法

### 调用示例

```python
# 创建 NetEase 实例
netease = NetEase()

# 获取播放链接
result = netease.songs_url_v1(
    ids=['123456', '789012'],  # 歌曲ID列表
    level='lossless',           # 音质级别
    source='tencent'            # 音源
)

# 解析结果
for item in result['data']:
    song_id = item['id']
    url = item['url']
    level = item['level']
    source = item['source']  # 'lxmusic', 'tunehub', 或 'netease'

    if url:
        print(f"歌曲 {song_id} 播放链接: {url} (来源: {source})")
    else:
        print(f"歌曲 {song_id} 获取失败")
```

### 支持的音源

| 音源名称 | source 参数 | LXMUSIC 标识符 | 优先级 |
|----------|-------------|----------------|--------|
| 网易云音乐 | netease | wy | TuneHub/网易云 |
| 腾讯音乐 | tencent | tx | LXMUSIC |
| 咪咕音乐 | migu | mg | LXMUSIC |
| 酷狗音乐 | kugou | kg | LXMUSIC |
| 酷我音乐 | kuwo | kw | LXMUSIC |
| JOOX 音乐 | joox | jm | LXMUSIC |
| Deezer | deezer | dp | LXMUSIC |
| 喜马拉雅 | ximalaya | xm | LXMUSIC |
| Apple Music | apple | ap | LXMUSIC |
| Spotify | spotify | sp | LXMUSIC |
| YouTube Music | ytmusic | yt | LXMUSIC |
| Qobuz | qobuz | qd | LXMUSIC |
| Tidal | tidal | td | LXMUSIC |

### 支持的音质

| 网易云 level | LXMUSIC quality | 说明 |
|-------------|-----------------|------|
| standard | 128k | 标准音质 |
| exceed | 320k | 超高音质 |
| high | 320k | 高音质 |
| lossless | flac | 无损音质 |
| hires | flac24bit | Hi-Res 音质 |
| dolby | atmos | 杜比全景声 |
| jyeffect | flac | 音效增强 |
| jymaster | master | 母带音质 |

## 日志输出

### 调试日志

所有操作都会输出详细的调试日志，便于问题排查：

```
plugin.audio.music: songs_url_v1 ids_list=['123456'] level=lossless source=tencent
plugin.audio.music: LXMUSIC source mapping: tencent -> tx, quality: lossless -> flac
plugin.audio.music: songs_url_v1 trying LXMUSIC id=123456 source=tx
plugin.audio.music: LXMUSIC 请求 URL: https://88.lxmusic.xn--fiqs8s/lxmusicv4/url/tx/123456/flac?sign=...
plugin.audio.music: LXMUSIC 响应数据: {'code': 0, 'data': 'https://...'}
plugin.audio.music: LXMUSIC 获取播放链接成功: https://...
plugin.audio.music: songs_url_v1 LXMUSIC success id=123456 url=https://...
plugin.audio.music: songs_url_v1 id=123456 url=https://... used_source=lxmusic
plugin.audio.music: songs_url_v1 final result_data=[{'id': '123456', 'url': 'https://...', 'level': 'lossless', 'source': 'lxmusic'}]
```

### 错误日志

如果 LXMUSIC 失败，会输出警告日志：

```
plugin.audio.music: songs_url_v1 LXMUSIC failed id=123456 error=LXMUSIC Key失效/鉴权失败
plugin.audio.music: songs_url_v1 trying TuneHub id=123456
```

## 错误处理

### LXMUSIC API 错误

| 错误代码 | 错误信息 | 处理方式 |
|----------|----------|----------|
| 0/200 | 成功 | 返回播放链接 |
| 403 | Key失效/鉴权失败 | 回退到 TuneHub |
| 429 | 请求过速 | 使用指数退避重试 |
| 404 | API端点不存在 | 回退到 TuneHub |
| 500+ | 服务器错误 | 回退到 TuneHub |

### 重试机制

- **最大重试次数**: 3 次
- **重试间隔**: 1 秒
- **429 错误退避**: 指数退避（最多 10 秒）

## 性能优化

### 1. 优先级策略

- 非 netease 音源优先使用 LXMUSIC（稳定性高）
- netease 音源直接使用 TuneHub/网易云（避免不必要的请求）

### 2. 缓存机制

- LXMUSIC API 本身支持缓存（通过请求头）
- 可以在 `songs_url_v1` 中添加本地缓存（可选）

### 3. 并发请求

- 当前为串行请求（逐个获取）
- 可以改为并发请求（使用 `concurrent.futures`）

## 测试建议

### 测试用例

```python
# 测试腾讯音乐（LXMUSIC 优先）
result = netease.songs_url_v1(ids=['123456'], level='lossless', source='tencent')

# 测试网易云音乐（TuneHub 优先）
result = netease.songs_url_v1(ids=['123456'], level='lossless', source='netease')

# 测试高音质
result = netease.songs_url_v1(ids=['123456'], level='hires', source='migu')

# 测试批量请求
result = netease.songs_url_v1(ids=['123456', '789012'], level='standard', source='kuwo')
```

### 验证要点

1. ✅ LXMUSIC API 能正常获取播放链接
2. ✅ 音质映射正确
3. ✅ 音源映射正确
4. ✅ 失败时能正确回退到 TuneHub
5. ✅ 日志输出完整
6. ✅ 错误处理正确

## 注意事项

### 1. API 限制

- LXMUSIC API 无官方文档，可能随时变动
- 建议定期测试 API 可用性
- 避免频繁请求（限流保护）

### 2. 音质兼容性

- 不同音源支持的音质不同
- 如果请求的音质不支持，API 可能返回错误
- 建议在调用前检查音源支持的音质列表

### 3. 版权声明

- 本集成仅供学习研究使用
- 请勿用于商业用途
- 请支持正版音乐

## 后续优化建议

### 1. 添加本地缓存

```python
@functools.lru_cache(maxsize=1000)
def _lxmusic_get_music_url_cached(self, source, songmid, quality):
    return self._lxmusic_get_music_url(source, songmid, quality)
```

### 2. 添加并发请求

```python
from concurrent.futures import ThreadPoolExecutor

def _get_urls_concurrent(self, ids_list):
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for _id in ids_list:
            future = executor.submit(self._get_single_url, _id)
            futures.append(future)
        return [f.result() for f in futures]
```

### 3. 添加健康检查

```python
def _lxmusic_health_check(self):
    """检查 LXMUSIC API 是否可用"""
    try:
        url = self._lxmusic_get_music_url('wy', '123456', '128k')
        return url is not None
    except:
        return False
```

## 更新日志

### 2026-01-29

- ✅ 集成 LXMUSIC API
- ✅ 添加音源映射
- ✅ 添加音质映射
- ✅ 实现优先级策略
- ✅ 添加详细日志
- ✅ 添加错误处理
- ✅ 添加重试机制

## 联系方式

如有问题，请提交 GitHub Issue。

---

**最后更新**: 2026-01-29
**API 版本**: v1.0
**插件版本**: v2.0.0
