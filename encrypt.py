#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, division, absolute_import
import base64
import binascii
import hashlib
import json
import os
import sys

from Cryptodome.Cipher import AES
from future.builtins import int, pow

PY3 = sys.version_info.major >= 3

__all__ = ["encrypted_id", "encrypted_request", "eapi_encrypt", "eapi_decrypt"]

MODULUS = (
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7"
    "b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280"
    "104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932"
    "575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b"
    "3ece0462db0a22b8e7"
)
PUBKEY = "010001"
NONCE = b"0CoJUm6Qyw8W8jud"


# 歌曲加密算法, 基于https://github.com/yanunon/NeteaseCloudMusic
def encrypted_id(id):
    magic = bytearray("3go8&$8*3*3h0k(2)2", "u8")
    song_id = bytearray(id, "u8")
    magic_len = len(magic)
    for i, sid in enumerate(song_id):
        song_id[i] = sid ^ magic[i % magic_len]
    m = hashlib.md5(song_id)
    result = m.digest()
    result = base64.b64encode(result).replace(b"/", b"_").replace(b"+", b"-")
    return result.decode("utf-8")

# 登录加密算法, 基于https://github.com/stkevintan/nw_musicbox
def encrypted_request(text):
    # type: (str) -> dict
    data = json.dumps(text).encode("utf-8")
    secret = create_key(16)
    params = aes(aes(data, NONCE), secret)
    encseckey = rsa(secret, PUBKEY, MODULUS)
    return {"params": params, "encSecKey": encseckey}

if PY3:
    def aes(text, key):
        pad = 16 - len(text) % 16
        text = text + bytearray([pad] * pad)
        encryptor = AES.new(key, 2, b"0102030405060708")
        ciphertext = encryptor.encrypt(text)
        return base64.b64encode(ciphertext)
else:
    def aes(text, key):
        pad = 16 - len(text) % 16
        text = text.encode() + bytearray([pad] * pad)
        encryptor = AES.new(key.encode(), 2, b"0102030405060708")
        ciphertext = encryptor.encrypt(str(text).encode())
        return base64.b64encode(ciphertext)



def rsa(text, pubkey, modulus):
    text = text[::-1]
    rs = pow(int(binascii.hexlify(text), 16), int(pubkey, 16), int(modulus, 16))
    return format(rs, "x").zfill(256)


def create_key(size):
    return binascii.hexlify(os.urandom(size))[:16]


# EAPI 加密算法 (用于上传播放记录等需要服务端实际处理的接口)
# 参考: https://github.com/Binaryify/NeteaseCloudMusicApi/blob/master/util/crypto.js
# eapi 使用 AES-128-ECB 加密，密钥为 e82ckenh8dichen8
EAPI_KEY = b'e82ckenh8dichen8'


def _eapi_aes_encrypt(data, key=EAPI_KEY):
    """EAPI AES-128-ECB 加密 with PKCS7 padding"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    pad = 16 - len(data) % 16
    data = data + bytes([pad] * pad)
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.encrypt(data)


def _eapi_aes_decrypt(data, key=EAPI_KEY):
    """EAPI AES-128-ECB 解密 with PKCS7 unpadding"""
    cipher = AES.new(key, AES.MODE_ECB)
    decrypted = cipher.decrypt(data)
    pad = decrypted[-1]
    return decrypted[:-pad]


def eapi_encrypt(url_path, data):
    """EAPI 加密请求

    Args:
        url_path: API 路径, 如 '/api/feedback/weblog'
        data: 请求参数 dict

    Returns:
        dict: {'params': hex_uppercase_encrypted_data}
    """
    text = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    message = 'nobody{}use{}md5forencrypt'.format(url_path, text)
    digest = hashlib.md5(message.encode('utf-8')).hexdigest()
    encrypt_text = '{}-36cd479b6b5-{}-36cd479b6b5-{}'.format(url_path, text, digest)
    encrypted = _eapi_aes_encrypt(encrypt_text)
    return {'params': encrypted.hex().upper()}


def eapi_decrypt(response_hex):
    """EAPI 解密响应

    Args:
        response_hex: hex 编码的加密响应

    Returns:
        dict: 解密后的 JSON 数据
    """
    raw = bytes.fromhex(response_hex)
    decrypted = _eapi_aes_decrypt(raw)
    return json.loads(decrypted.decode('utf-8'))
