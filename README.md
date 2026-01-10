更新日志 — 2026-01-10
-------------------

本次提交主要针对 TuneHub 集成与搜索/播放体验的改进：

```markdown
更新日志 — 2026-01-10
-------------------

本次提交主要針對 TuneHub 集成與搜索/播放體驗的改進：

- `api.py`
  - `tunehub_toplists(self, source=None, type='toplists')`：簽名調整以兼容多平台輸入，維持向後兼容性。
  - 對 TuneHub 返回結構增加兼容分支（處理 `list` / `data` / `tracks` 等不同字段）。
  - `tunehub_request`：改進請求 headers 處理，減少因 Host/Referer 不匹配導致的 403 情況。
  - 新增 `_normalize_tunehub_pics(resp)`：統一填充 `pic` 候選字段以供前端顯示封面。

- `addon.py`
  - `tunehub_toplists` 路由：在打開排行榜時支援選擇平台（`网易云/QQ/酷我`），並將 `source` 傳給後端。
  - 搜索/聚合結果：優先使用 `pic` 字段，填充 `thumbnail` 與 `icon` 以顯示封面。
  - `tunehub_play`：在播放時透過 `music.tunehub_info` 取得更完整 metadata，建立 `ListItem`（使用 `InfoTagMusic`）並透過播放器展示。

測試與注意事項：
- 已改進 403 處理與日志；若仍頻繁出現 403，請檢查網路/代理或考慮使用代理中轉。

---

更新日志 — 2026-01-11
-------------------

今日對插件做出的關鍵改動（概要）：

- `addon.py`
  - 修復並初始化 `music = NetEase()`，解決啟動時未定義錯誤。
  - 修正多處 `try/except` 縮進與異常處理，確保在構建 `ListItem` 成功或失敗時均會執行解析/resolve 流程。
  - 在 `tunehub_play` 添加更詳細的調試日誌（輸出 `sys.argv`、handle、url 長度與 host），便於定位 Kodi 拒絕 resolved item 的原因。
  - 新增基於 host 的回退策略：對 QQ 源（如 `qqmusic.qq.com` / `stream.qqmusic.qq.com` / `isure6.stream.qqmusic.qq.com`）在 setResolvedUrl 可能被拒絕時直接回退使用 `PlayMedia` 進行播放。
  - 刪除 play-all 路由（按使用者要求）並恢復簡潔的 `setResolvedUrl` + fallback 行爲。
  - 優先使用 `ListItem.getMusicInfoTag()` / `InfoTagMusic` 設置元數據，減少對過時 `setInfo()` 的依賴。

- 歌單播放（`play_recommend_songs` / `play_playlist_songs`）
  - 實現「延遲解析」策略：打開歌單時不再立即請求每首歌的播放地址，而是將 plugin 路徑加入 `xbmc.PlayList`（保留 `ListItem` 元數據），由 Kodi 在播放時呼叫插件的 `play()` 路由再去獲取真實播放 URL。這樣可以加快打開速度並避免因 vkey 過期導致的播放失敗。

- TuneHub / `api.py` 相關
  - 保留從響應(respond)物件 (`resp.url`) 提取最終 mp3 鏈接的邏輯，以處理 TuneHub 返回非 JSON（直接重定向或直接返回音頻）時的情況。
  - 在遇到 403 時記錄日誌（JSON 解析失敗後仍嘗試使用 `resp.url`），建議後續可選做法：增加重試、補充請求頭、或採用代理中轉以提高穩定性。

測試與後續建議：
- 日誌中已加入更多調試資訊（setResolvedUrl 調用、handle、解析 URL 信息等），請在運行環境觀察是否仍有 “Error resolving item” 訊息。
- 若頻繁出現 403 或播放失敗：
  - 可為 TuneHub 請求加入可配置的頭信息並添加有限次數的重試；
  - 或在後端/本地實現輕量代理轉發以穩定請求行為和頭信息。

---

若你希望我將這些改動合入版本控制（commit）並執行進一步本地測試，我可以繼續處理。

```
