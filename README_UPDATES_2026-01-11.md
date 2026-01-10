更新日志 — 2026-01-11
-------------------

今日对插件做出的关键改动（概要）：

- `addon.py`
  - 修复并初始化 `music = NetEase()`，解决启动时报错。
  - 修正若干 `try/except` 缩进与异常处理问题，确保在构建 `ListItem` 成功或失败时都会执行解析/resolve 流程。
  - 在 `tunehub_play` 添加更详细调试日志（输出 `sys.argv`、handle、url 长度与 host），便于定位 Kodi 拒绝 resolved item 的原因。
  - 导入 `urlparse` 并基于 host 做回退：针对 QQ 源在 setResolvedUrl 失败场景下直接使用 `PlayMedia` 回退播放。
  - 删除了 play-all 路由（按用户要求）并恢复更简洁的 setResolvedUrl + fallback 行为。
  - 优先通过 `ListItem.getMusicInfoTag()`/`InfoTagMusic` 设置元数据，减小对过时 `setInfo()` 的依赖。

- 歌单播放（`play_recommend_songs` / `play_playlist_songs`）
  - 实现“延迟解析”策略：打开歌单时不再为每首歌立即请求播放地址，而是把 plugin 路径加入 `xbmc.PlayList`（保留 `ListItem` 元数据），由 Kodi 在播放时调用插件的 `play()` 路由再去获取真实播放 URL（避免打开时大量请求与 vkey 过期问题）。

- TuneHub / `api.py` 相关
  - 保留从响应对象 (`resp.url`) 提取最终 mp3 链接的逻辑，以处理 TuneHub 返回非 JSON（重定向或直接返回音频）的情况。
  - 在遇到 403 的场景时记录日志（JSON 解析失败后仍可尝试使用 `resp.url`），并建议后续可选：增加请求头、重试或走代理转发以提高稳定性。

测试与后续建议：
- 已增加调试日志以便观测 `setResolvedUrl` 调用和 Kodi 的响应；请在运行环境下观察是否仍有 “Error resolving item” 日志。
- 若频繁出现 403 或无法播放的条目，我可以：
  - 为 TuneHub 请求添加可配置的请求头并加入重试逻辑；
  - 或实现一个轻量级代理转发以统一并稳定请求头/重定向逻辑。

备注：尝试直接更新 `README.md` 时遇到编辑接口错误，我已将改动写入此文件 `README_UPDATES_2026-01-11.md`，如需我继续尝试把内容合并回 `README.md`，我可以再尝试一次或由你确认接纳此文件内容后我再继续。