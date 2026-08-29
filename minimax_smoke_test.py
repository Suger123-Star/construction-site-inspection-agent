# -*- coding: utf-8 -*-
"""MiniMax API 连通性冒烟测试。

用法（在项目目录下）：
    python minimax_smoke_test.py             # 文本 + 视觉 + 语音 三项真实调用
    python minimax_smoke_test.py --text      # 仅测试文本模型
    python minimax_smoke_test.py --vision    # 仅测试 MiniMax-M3 视觉
    python minimax_smoke_test.py --tts       # 仅测试 speech-2.8-turbo 语音
    python minimax_smoke_test.py --sdk       # 用官方 OpenAI SDK 调文本/视觉

前置条件：
    1) 已复制 .env.example 为 .env 并填入 MINIMAX_API_KEY
    2) python -m pip install -r requirements.txt

未配置 Key 时脚本只打印提示，不会发起网络请求，并以退出码 0 结束。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass


def env(key: str, default: str = "") -> str:
    value = os.getenv(key, default)
    return (value or default).strip()


API_KEY = env("MINIMAX_API_KEY")
BASE_URL = env("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
TEXT_MODEL = env("MINIMAX_TEXT_MODEL", "MiniMax-M2")
VISION_MODEL = env("MINIMAX_VISION_MODEL", "MiniMax-M3")
TTS_MODEL = env("MINIMAX_TTS_MODEL", "speech-2.8-turbo")
TTS_URL = env("MINIMAX_TTS_URL", "https://api.minimaxi.com/v1/t2a_v2")
ANTHROPIC_BASE_URL = env("MINIMAX_ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def _post(url: str, payload: dict, timeout: int = 90) -> dict:
    import requests
    resp = requests.post(url, headers=_headers(), json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def test_text() -> bool:
    import requests
    print(f"\n[1/3] 文本模型 {TEXT_MODEL}")
    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": "你是建筑工地安全巡检助手，回答要简短。"},
            {"role": "user", "content": "请用一句话说明你的职责。"},
        ],
        "temperature": 0.2,
    }
    try:
        data = _post(f"{BASE_URL}/chat/completions", payload)
        text = data["choices"][0]["message"].get("content") or ""
        print("  OK:", text.strip()[:160])
        return bool(text.strip())
    except Exception as exc:
        print("  FAIL:", exc)
        return False


def test_vision() -> bool:
    import requests
    print(f"\n[2/3] 视觉模型 {VISION_MODEL}")
    image = next(ASSETS.glob("site_demo*.png"), None) if ASSETS.exists() else None
    if image is None:
        print("  SKIP: 未找到 assets/site_demo*.png 示例图片")
        return True
    b64 = base64.b64encode(image.read_bytes()).decode("ascii")
    data_url = f"data:image/png;base64,{b64}"
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "这是工地现场图。只输出 JSON：{\"summary\":\"一句话\",\"findings\":[{\"item\":\"隐患项\",\"status\":\"状态\",\"confidence\":0.9,\"risk_level\":\"高\",\"needs_review\":false}]}。"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "thinking": {"type": "adaptive"},
        "max_completion_tokens": 600,
    }
    try:
        data = _post(f"{BASE_URL}/chat/completions", payload)
        content = data["choices"][0]["message"].get("content") or ""
        print("  OK:", content.strip()[:200])
        return True
    except Exception as exc:
        print("  FAIL:", exc)
        return False


def test_tts() -> bool:
    import requests
    print(f"\n[3/3] 语音合成 {TTS_MODEL}")
    payload = {
        "model": TTS_MODEL,
        "text": "请立即佩戴安全帽，并系紧下颚带。",
        "voice_setting": {"voice_id": "male-qn-qingse", "speed": 1.0, "vol": 1.0},
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3"},
    }
    try:
        data = _post(TTS_URL, payload)
        audio_hex = (data.get("data") or {}).get("audio", "")
        if not audio_hex:
            print("  FAIL: 返回中没有 audio 字段")
            return False
        out = ROOT / "data" / "tts_smoke.mp3"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(bytes.fromhex(audio_hex))
        print(f"  OK: 已保存 {out} ({out.stat().st_size} 字节)")
        return True
    except Exception as exc:
        print("  FAIL:", exc)
        return False


def test_openai_sdk() -> bool:
    print("\n[SDK] 使用官方 OpenAI SDK 调用 MiniMax（OpenAI 兼容接口）")
    try:
        from openai import OpenAI
    except Exception as exc:
        print("  FAIL: 未安装 openai，请先运行 python -m pip install openai")
        return False
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    try:
        resp = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role": "user", "content": "用一句话说明 MiniMax API 已连通。"}],
            max_tokens=60,
        )
        text = resp.choices[0].message.content or ""
        print("  OK:", text.strip()[:160])
        return bool(text.strip())
    except Exception as exc:
        print("  FAIL:", exc)
        return False


def test_anthropic_sdk() -> bool:
    print("\n[SDK] 使用官方 Anthropic SDK 调用 MiniMax（Anthropic 兼容接口）")
    try:
        import anthropic
    except Exception:
        print("  FAIL: 未安装 anthropic，请先运行 python -m pip install anthropic")
        return False
    client = anthropic.Anthropic(api_key=API_KEY, base_url=ANTHROPIC_BASE_URL)
    try:
        resp = client.messages.create(
            model=TEXT_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": "用一句话说明 MiniMax Anthropic 接口已连通。"}],
        )
        text = "".join(getattr(b, "text", "") or "" for b in resp.content if getattr(b, "type", "") == "text").strip()
        if text:
            print("  OK:", text[:160])
        else:
            print("  OK: 请求成功（本次未返回文本块）")
        return True
    except Exception as exc:
        print("  FAIL:", exc)
        return False

def main() -> int:
    print("=" * 64)
    print("MiniMax API 连通性冒烟测试")
    print(f"BASE_URL = {BASE_URL}")
    print(f"文本模型 = {TEXT_MODEL} | 视觉模型 = {VISION_MODEL} | 语音模型 = {TTS_MODEL}")
    args = _parse_args()

    if not API_KEY or API_KEY.startswith("sk-xxxx"):
        print("\n未检测到有效的 MINIMAX_API_KEY。")
        print("请先复制 .env.example 为 .env 并填入真实 API Key，然后重新运行本脚本。")
        print("（本脚本不会在无 Key 时发起网络请求）")
        return 0
    results: list[bool] = []
    if args.anthropic:
        results.append(test_anthropic_sdk())
    elif args.sdk:
        results.append(test_openai_sdk())
    else:
        if args.text:
            results.append(test_text())
        if args.vision:
            results.append(test_vision())
        if args.tts:
            results.append(test_tts())

    print("\n" + "=" * 64)
    ok = all(results) and bool(results)
    print("结果:", "全部通过 ✔" if ok else "存在失败项，请检查上方输出")
    return 0 if ok else 2


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MiniMax API 冒烟测试")
    p.add_argument("--text", action="store_true", help="仅测试文本模型")
    p.add_argument("--vision", action="store_true", help="仅测试 MiniMax-M3 视觉")
    p.add_argument("--tts", action="store_true", help="仅测试 speech-2.8-turbo 语音")
    p.add_argument("--sdk", action="store_true", help="使用官方 OpenAI SDK 测试")
    p.add_argument("--anthropic", action="store_true", help="使用官方 Anthropic SDK 测试")
    args = p.parse_args()
    if not (args.text or args.vision or args.tts or args.sdk or args.anthropic):
        args.text = args.vision = args.tts = True
    return args


if __name__ == "__main__":
    sys.exit(main())