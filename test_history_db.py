#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试播放历史记录数据库功能
"""

import sys
import os

# 添加插件路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cache import (
    get_cache_db,
    add_play_history,
    get_play_history,
    clear_play_history,
    get_play_history_by_artist,
    get_play_history_by_album
)


def test_history_db():
    """测试历史记录数据库功能"""
    print("=" * 60)
    print("测试播放历史记录数据库功能")
    print("=" * 60)

    # 1. 清空历史记录
    print("\n1. 清空历史记录...")
    clear_play_history()
    history = get_play_history()
    print(f"   历史记录数量: {len(history)}")
    assert len(history) == 0, "清空失败"
    print("   ✓ 清空成功")

    # 2. 添加测试数据
    print("\n2. 添加测试数据...")
    test_songs = [
        {
            "song_id": 1,
            "song_name": "测试歌曲1",
            "artist": "测试歌手A",
            "artist_id": 101,
            "album": "测试专辑X",
            "album_id": 201,
            "pic": "https://example.com/pic1.jpg",
            "duration": 180
        },
        {
            "song_id": 2,
            "song_name": "测试歌曲2",
            "artist": "测试歌手A",
            "artist_id": 101,
            "album": "测试专辑X",
            "album_id": 201,
            "pic": "https://example.com/pic2.jpg",
            "duration": 200
        },
        {
            "song_id": 3,
            "song_name": "测试歌曲3",
            "artist": "测试歌手B",
            "artist_id": 102,
            "album": "测试专辑Y",
            "album_id": 202,
            "pic": "https://example.com/pic3.jpg",
            "duration": 220
        },
    ]

    for song in test_songs:
        add_play_history(**song)
        print(f"   添加: {song['song_name']} - {song['artist']}")

    # 3. 获取所有历史记录
    print("\n3. 获取所有历史记录...")
    history = get_play_history()
    print(f"   历史记录数量: {len(history)}")
    for h in history:
        print(f"   - {h['name']} - {h['artist']} (ID: {h['id']})")
    assert len(history) == 3, "获取历史记录失败"
    print("   ✓ 获取成功")

    # 4. 测试按艺术家查询
    print("\n4. 测试按艺术家查询...")
    artist_history = get_play_history_by_artist("测试歌手A")
    print(f"   测试歌手A 的歌曲数量: {len(artist_history)}")
    for h in artist_history:
        print(f"   - {h['name']}")
    assert len(artist_history) == 2, "按艺术家查询失败"
    print("   ✓ 按艺术家查询成功")

    # 5. 测试按专辑查询
    print("\n5. 测试按专辑查询...")
    album_history = get_play_history_by_album("测试专辑X")
    print(f"   测试专辑X 的歌曲数量: {len(album_history)}")
    for h in album_history:
        print(f"   - {h['name']}")
    assert len(album_history) == 2, "按专辑查询失败"
    print("   ✓ 按专辑查询成功")

    # 6. 测试按天数过滤
    print("\n6. 测试按天数过滤...")
    recent_history = get_play_history(days=7)
    print(f"   最近7天的歌曲数量: {len(recent_history)}")
    assert len(recent_history) == 3, "按天数过滤失败"
    print("   ✓ 按天数过滤成功")

    # 7. 测试限制数量
    print("\n7. 测试限制数量...")
    limited_history = get_play_history(limit=2)
    print(f"   限制2首的歌曲数量: {len(limited_history)}")
    assert len(limited_history) == 2, "限制数量失败"
    print("   ✓ 限制数量成功")

    # 8. 测试去重（重复添加同一首歌）
    print("\n8. 测试去重...")
    add_play_history(
        song_id=1,
        song_name="测试歌曲1",
        artist="测试歌手A",
        artist_id=101,
        album="测试专辑X",
        album_id=201,
        pic="https://example.com/pic1.jpg",
        duration=180
    )
    history = get_play_history()
    print(f"   重复添加后的历史记录数量: {len(history)}")
    assert len(history) == 3, "去重失败"
    print("   ✓ 去重成功")

    # 9. 清空测试数据
    print("\n9. 清空测试数据...")
    clear_play_history()
    history = get_play_history()
    print(f"   清空后的历史记录数量: {len(history)}")
    assert len(history) == 0, "清空失败"
    print("   ✓ 清空成功")

    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    test_history_db()
