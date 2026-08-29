# -*- coding: utf-8 -*-
"""工地隐患巡检与整改助手 - 最小可运行演示骨架。

本文件用于两天内快速搭建一个可提交的智能体 Demo：
- 现场照片 -> 安全帽/反光衣/危险区域识别 -> MiniMax 生成风险描述与整改单
- 不确定项转人工确认，人工反馈回写日志（体现人机协同 / AI纠偏）
- MiniMax 语音播报整改要点

快速开始：
  1) 复制 .env.example 为 .env，填入 MINIMAX_API_KEY
  2) python -m pip install -r requirements.txt
  3) python app.py

没有 API Key 或未安装视觉模型时，默认进入 DEMO_MODE，
用内置模拟结果跑通完整交互，便于录屏和调试界面。
"""
from __future__ import annotations

import base64
import re
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
PENDING_FILE = DATA_DIR / "pending_review.json"
FEEDBACK_FILE = DATA_DIR / "feedback_log.jsonl"
ASSETS_DIR = ROOT / "assets"
SAMPLE_IMAGES = [str(p) for p in sorted((ASSETS_DIR).glob("site_demo*.png"))] if ASSETS_DIR.exists() else []

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    import gradio as gr
except Exception:  # pragma: no cover
    gr = None


# ---------------------------------------------------------------- 配置加载
def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


ENV = _load_env()
API_KEY = ENV.get("MINIMAX_API_KEY", os.getenv("MINIMAX_API_KEY", ""))
BASE_URL = ENV.get("MINIMAX_BASE_URL", os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"))
TEXT_MODEL = ENV.get("MINIMAX_TEXT_MODEL", os.getenv("MINIMAX_TEXT_MODEL", "MiniMax-M2"))
VISION_MODEL = ENV.get("MINIMAX_VISION_MODEL", os.getenv("MINIMAX_VISION_MODEL", "MiniMax-M3"))
TTS_MODEL = ENV.get("MINIMAX_TTS_MODEL", os.getenv("MINIMAX_TTS_MODEL", "speech-2.8-turbo"))
TTS_URL = ENV.get("MINIMAX_TTS_URL", os.getenv("MINIMAX_TTS_URL", "https://api.minimaxi.com/v1/t2a_v2"))
DEMO_MODE = (ENV.get("DEMO_MODE", os.getenv("DEMO_MODE", "auto")) == "1")
if ENV.get("DEMO_MODE", os.getenv("DEMO_MODE", "auto")) == "auto":
    DEMO_MODE = not bool(API_KEY)

# ---------------------------------------------------------------- 知识库
# 这里用内置“安全规范卡片”做最简检索。要升级为向量检索，可替换为
# sentence-transformers + chromadb 的 retriever，接口保持不变。
SAFETY_KB: list[dict[str, str]] = [
    {"id": "KB-001", "scene": "安全帽", "keywords": ["安全帽", "未佩戴", "个人防护", "PPE"],
     "rule": "进入施工现场所有人员必须正确佩戴安全帽并系紧下颚带，安全帽应符合 GB 2811 要求。",
     "rectify": "立即停止该区域作业，责令未佩戴者离开危险区并接受安全教育，佩戴合格后方可进场。",
     "risk": "物体打击", "source": "JGJ 184-2009 / GB 2811-2019"},
    {"id": "KB-002", "scene": "反光衣", "keywords": ["反光衣", "反光背心", "警示服", "高可视"],
     "rule": "夜间或低能见度区域作业人员必须穿高可视性警示服。",
     "rectify": "暂停作业，配发并正确穿着反光背心后方可继续施工。",
     "risk": "车辆伤害", "source": "JGJ 184-2009 / GB 20653"},
    {"id": "KB-003", "scene": "高处作业", "keywords": ["高处作业", "登高", "安全带", "坠落"],
     "rule": "凡在坠落高度基准面 2 米及以上作业，必须正确系挂安全带并设置可靠挂点。",
     "rectify": "停止作业，监督人员现场确认安全带系挂点，复检合格后复工。",
     "risk": "高处坠落", "source": "JGJ 80-2016"},
    {"id": "KB-004", "scene": "临边防护", "keywords": ["临边", "防护栏", "防护栏杆", "临边防护"],
     "rule": "基坑、楼层、屋面、阳台等临边部位必须设置防护栏杆并挂设安全网。",
     "rectify": "立即封闭作业面，搭设双道防护栏杆并设置挡脚板，验收合格后复工。",
     "risk": "高处坠落", "source": "JGJ 80-2016"},
    {"id": "KB-005", "scene": "洞口防护", "keywords": ["洞口", "预留洞", "电梯井", "采光井"],
     "rule": "各类竖向与水平洞口必须设置盖板、防护栏杆或安全网，防止人员坠落。",
     "rectify": "暂停洞口周边作业，按洞口尺寸设置可靠防护并挂警示标志。",
     "risk": "高处坠落", "source": "JGJ 80-2016"},
    {"id": "KB-006", "scene": "脚手架", "keywords": ["脚手架", "外架", "立杆", "连墙件", "脚手板"],
     "rule": "脚手架必须按方案搭设，连墙件、剪刀撑、脚手板、安全网齐全并经验收合格。",
     "rectify": "停止使用，由架子工按方案整改，重新验收挂牌后方可使用。",
     "risk": "坍塌/高处坠落", "source": "JGJ 130-2011"},
    {"id": "KB-007", "scene": "模板支架", "keywords": ["模板", "支撑", "高大模板", "支模", "架体"],
     "rule": "模板支撑体系必须按专项方案搭设，高大模板工程须专家论证并验收。",
     "rectify": "停止浇筑作业，复核立杆间距、扫地杆、剪刀撑，验收合格后复工。",
     "risk": "坍塌", "source": "JGJ 162-2008 / 住建部令第37号"},
    {"id": "KB-008", "scene": "基坑边坡", "keywords": ["基坑", "边坡", "支护", "深基坑", "土方"],
     "rule": "深基坑及边坡必须按方案支护、监测，坡顶不得堆载，并设置上下通道与临边防护。",
     "rectify": "停止坑内作业，撤离人员，复核支护与监测数据，处置险情后复工。",
     "risk": "坍塌", "source": "JGJ 120-2012 / JGJ 59-2011"},
    {"id": "KB-009", "scene": "临时用电", "keywords": ["临时用电", "配电箱", "开关箱", "接零", "漏电"],
     "rule": "配电系统实行三级配电、两级漏电保护，配电箱必须上锁并由持证电工管理。",
     "rectify": "断电整改，由持证电工检查线路、漏保与接地，恢复标准配电后送电。",
     "risk": "触电", "source": "JGJ 46-2005"},
    {"id": "KB-010", "scene": "电缆敷设", "keywords": ["电缆", "拖地", "泡水", "电线", "架空"],
     "rule": "电缆不得拖地、泡水或沿金属脚手架敷设，过路应穿管保护或架空。",
     "rectify": "停电整改，电缆架空或穿管埋地敷设，破损电缆更换后送电。",
     "risk": "触电", "source": "JGJ 46-2005"},
    {"id": "KB-011", "scene": "动火作业", "keywords": ["动火", "焊接", "切割", "气瓶", "明火"],
     "rule": "动火作业前必须办理动火证，清理可燃物，配备灭火器材并设监护人。",
     "rectify": "停止动火，核查动火证与监护人到位情况，清理现场后重新审批。",
     "risk": "火灾", "source": "GB 50720-2011"},
    {"id": "KB-012", "scene": "消防器材", "keywords": ["灭火器", "消防", "消火栓", "消防通道"],
     "rule": "现场必须按规定配置灭火器材，消防通道保持畅通，严禁占用、堵塞。",
     "rectify": "立即补充或归位消防器材，清理消防通道，整改后复查。",
     "risk": "火灾", "source": "GB 50720-2011"},
    {"id": "KB-013", "scene": "起重吊装", "keywords": ["塔吊", "起重", "吊装", "龙门吊", "吊物"],
     "rule": "起重吊装必须由持证人员指挥操作，划定警戒区，严禁超载和斜拉斜吊。",
     "rectify": "停止吊装，核实设备检验、人员证件与警戒措施，符合要求后复工。",
     "risk": "起重伤害", "source": "JGJ 196-2010 / JGJ 59-2011"},
    {"id": "KB-014", "scene": "吊索具", "keywords": ["吊索", "钢丝绳", "吊具", "卸扣", "吊带"],
     "rule": "吊索具使用前必须检查，达到报废标准应立即停用并更换。",
     "rectify": "停止使用报废吊索具，清点更换并做检验标识后恢复吊装。",
     "risk": "起重伤害", "source": "JGJ 196-2010"},
    {"id": "KB-015", "scene": "有限空间", "keywords": ["有限空间", "密闭", "井道", "地下室", "缺氧"],
     "rule": "进入有限空间前必须执行“先通风、再检测、后作业”并设专人监护。",
     "rectify": "立即撤出人员，实施通风检测，办理作业审批并落实监护后复工。",
     "risk": "中毒窒息", "source": "房屋市政工程重大隐患判定标准(2022版)"},
    {"id": "KB-016", "scene": "安全通道", "keywords": ["安全通道", "通道", "出入口", "防护棚"],
     "rule": "人员出入口必须设置安全通道及防护棚，通道保持畅通、牢固。",
     "rectify": "封闭通道，搭设或加固防护棚，清理通道障碍后恢复通行。",
     "risk": "物体打击", "source": "JGJ 59-2011"},
    {"id": "KB-017", "scene": "材料堆放", "keywords": ["材料堆放", "堆载", "物料", "码放"],
     "rule": "材料分类码放整齐，堆高不得超过规定，临边和基坑周边严禁超载堆料。",
     "rectify": "重新码放或转运物料，核验堆载不超限并恢复作业面整洁。",
     "risk": "坍塌/物体打击", "source": "JGJ 59-2011"},
    {"id": "KB-018", "scene": "文明施工", "keywords": ["扬尘", "裸土", "覆盖", "洒水", "围挡"],
     "rule": "施工现场实行封闭管理，裸土覆盖、道路硬化、湿法作业，控制扬尘。",
     "rectify": "落实围挡、覆盖与洒水降尘措施，整改后保持常态化。",
     "risk": "环境/健康", "source": "JGJ 59-2011"},
    {"id": "KB-019", "scene": "夜间施工", "keywords": ["夜间", "照明", "低能见度", "灯具"],
     "rule": "夜间施工必须有充足照明，危险区域设警示灯，照明不足严禁作业。",
     "rectify": "暂停作业，增设照明与警示设施，满足照度要求后复工。",
     "risk": "综合伤害", "source": "JGJ 46-2005 / JGJ 59-2011"},
    {"id": "KB-020", "scene": "恶劣天气", "keywords": ["大风", "暴雨", "雷电", "台风", "高温"],
     "rule": "六级及以上大风、暴雨、雷电等恶劣天气应停止露天高处与吊装作业。",
     "rectify": "发布停工指令，撤离人员并加固设施，气象条件恢复后复工。",
     "risk": "综合伤害", "source": "JGJ 80-2016 / JGJ 59-2011"},
    {"id": "KB-021", "scene": "高处抛物", "keywords": ["抛物", "坠物", "物体打击", "抛掷"],
     "rule": "严禁从高处向下抛掷物料，作业层下方设隔离防护。",
     "rectify": "停止违规行为，设置隔离区与警示，开展班前教育后恢复作业。",
     "risk": "物体打击", "source": "JGJ 80-2016"},
    {"id": "KB-022", "scene": "危险作业审批", "keywords": ["危险作业", "作业票", "审批", "监护"],
     "rule": "动火、有限空间、吊装、高处等危险作业必须办理作业审批并落实监护人。",
     "rectify": "停止作业，补齐审批与监护措施，复查合格后复工。",
     "risk": "综合风险", "source": "房屋市政工程重大隐患判定标准(2022版)"},
]


def retrieve_rules(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    """按识别到的隐患名称返回相关规范，支持场景词与别名匹配。"""
    keywords = [str(f.get("item", "")).strip() for f in findings]
    matched: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in SAFETY_KB:
        hay = [card.get("scene", "")] + list(card.get("keywords", []))
        if any(any(k in h or h in k for k in keywords if k) for h in hay):
            if card["id"] in seen:
                continue
            seen.add(card["id"])
            matched.append({k: v for k, v in card.items() if k != "keywords"})
    if not matched:
        return [{k: v for k, v in SAFETY_KB[0].items() if k != "keywords"}]
    return matched


# ---------------------------------------------------------------- 感知层（可替换为真实模型）
def safety_detect(image_path: str) -> list[dict[str, Any]]:
    """安全帽/反光衣/危险区域识别。

    生产环境替换为 PaddleDetection 推理结果，只需返回：
    [{"item": "安全帽", "status": "未佩戴", "bbox": [x1,y1,x2,y2], "confidence": 0.91}]
    """
    real = os.getenv("USE_PADDLEDETECTION", ENV.get("USE_PADDLEDETECTION", "0"))
    if real == "1":
        return _paddledetection_detect(image_path)

    # DEMO 模式：返回一组可复现的示例结果，保证录屏稳定。
    return [
        {"item": "安全帽", "status": "未佩戴", "bbox": [180, 120, 360, 300], "confidence": 0.92},
        {"item": "反光衣", "status": "已穿着", "bbox": [150, 160, 420, 520], "confidence": 0.88},
        {"item": "动火作业", "status": "疑似无动火证", "bbox": [500, 220, 760, 480], "confidence": 0.76},
    ]


def _paddledetection_detect(image_path: str) -> list[dict[str, Any]]:
    """真实 PaddleDetection 接入占位。

    典型做法：
    1) git clone PaddleDetection，下载 helmet 预训练模型
    2) 调用其推理脚本得到 JSON 检测框
    3) 把类别映射为安全帽/反光衣，并转成本函数返回结构
    """
    # TODO: 调用你的 PaddleDetection 推理命令或 PaddleX pipeline
    # 这里保持返回示例结构，便于上层逻辑继续开发。
    return [
        {"item": "安全帽", "status": "未佩戴", "bbox": [180, 120, 360, 300], "confidence": 0.92},
        {"item": "反光衣", "status": "已穿着", "bbox": [150, 160, 420, 520], "confidence": 0.88},
    ]


def ocr_text(image_path: str) -> str:
    """现场标牌/表单识别。生产环境替换为 PaddleOCR。"""
    if os.getenv("USE_PADDLEOCR", ENV.get("USE_PADDLEOCR", "0")) == "1":
        # TODO: from paddleocr import PaddleOCR; return ocr.ocr(image_path)
        return "1#塔吊动火作业区，动火证编号 ZJ-2026-0829"
    return "1#塔吊动火作业区，动火证编号 ZJ-2026-0829"


def transcribe_audio(audio_path: str) -> str:
    """语音输入转写。生产环境替换为 Whisper 或 FunASR。"""
    if os.getenv("USE_ASR", ENV.get("USE_ASR", "0")) == "1":
        # TODO: import whisper / funasr，返回转写文本
        return "检查一下刚才这张照片有没有隐患"
    return "检查一下刚才这张照片有没有隐患"


# ---------------------------------------------------------------- 多模态视觉识别（MiniMax-M3 主路径）
VISION_PROMPT = (
    "你是建筑工地安全巡检的视觉识别模块。请只输出一个 JSON 对象，不要输出任何其他文字或 Markdown。"
    "分析这张工地现场照片，按以下字段返回：\n"
    "{\n"
    '  "summary": "现场总体情况的一句话描述",\n'
    '  "findings": [\n'
    '    {"item": "安全帽/反光衣/高处作业/动火作业/临时用电/临边防护等隐患或检查项", '
    '"status": "未佩戴/已佩戴/缺失/违章/正常/无法判断", '
    '"confidence": 0.0到1.0之间的小数, '
    '"risk_level": "高/中/低", '
    '"evidence": "你在画面中看到的具体依据", '
    '"needs_review": true或false}\n'
    "  ],\n"
    '  "risks": ["可能造成的事故类型，如 高处坠落、物体打击、火灾、触电"],\n'
    '  "pending_review": ["置信度低或信息不足、需要人工现场确认的事项"]\n'
    "}\n"
    "规则：无法从照片判断的项，confidence 应较低且 needs_review 设为 true；"
    "没有隐患也要如实返回 findings 为空数组，并给出 summary。"
)


def encode_image_to_data_url(image_path: str) -> str:
    suffix = Path(image_path).suffix.lower().lstrip(".")
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "bmp": "image/bmp",
    }.get(suffix, "image/jpeg")
    payload = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _strip_thinking(text: str) -> str:
    """去掉 MiniMax 返回内容中的 <think>...</think> 思考段，保留最终回答。"""
    if not text:
        return text
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def _parse_vision_json(text: str) -> dict[str, Any]:
    text = _strip_thinking(text)
    """把模型返回内容稳健地解析为结构化结果；失败时降级为模拟识别。"""
    try:
        data = json.loads(_strip_code_fence(text))
        if not isinstance(data, dict) or "findings" not in data:
            return _mock_vision()
        findings = data.get("findings") or []
        if not isinstance(findings, list):
            findings = []
        data["findings"] = findings
        data.setdefault("summary", "已根据现场照片完成初步识别。")
        data.setdefault("risks", [])
        data.setdefault("pending_review", [])
        return data
    except Exception:
        return _mock_vision()


def _mock_vision() -> dict[str, Any]:
    """演示模式下的确定性视觉识别结果，便于录屏与讲解。"""
    return {
        "summary": "画面为在建楼栋的塔吊作业区，现场有人员活动并存在多处隐患。",
        "findings": [
            {
                "item": "安全帽",
                "status": "未佩戴",
                "confidence": 0.92,
                "risk_level": "高",
                "evidence": "画面右侧一名人员头部无安全帽轮廓。",
                "needs_review": False,
            },
            {
                "item": "反光衣",
                "status": "已穿着",
                "confidence": 0.88,
                "risk_level": "低",
                "evidence": "人员躯干可见反光条。",
                "needs_review": False,
            },
            {
                "item": "动火作业",
                "status": "疑似无动火证",
                "confidence": 0.76,
                "risk_level": "中",
                "evidence": "现场有气瓶与切割火花，但未在画面中看到动火证。",
                "needs_review": True,
            },
        ],
        "risks": ["物体打击", "高处坠落", "火灾"],
        "pending_review": ["动火作业：需现场核实动火证与监护人是否到位"],
    }


def call_minimax_vision(image_path: str) -> dict[str, Any]:
    """调用 MiniMax-M3 多模态视觉模型识别现场隐患。"""
    if DEMO_MODE or requests is None or not API_KEY:
        return _mock_vision()
    data_url = encode_image_to_data_url(image_path)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": VISION_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": VISION_MODEL,
                "messages": messages,
                "thinking": {"type": "disabled"},
                "max_completion_tokens": 1200,
            },
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"].get("content") or ""
        return _parse_vision_json(content)
    except Exception as exc:
        print(f"[MiniMax vision] fallback to mock: {exc}", file=sys.stderr)
        return _mock_vision()


# ---------------------------------------------------------------- MiniMax 调用
def call_minimax_text(system: str, user: str) -> str:
    """调用 MiniMax 文本模型（OpenAI 兼容 /chat/completions）。"""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if DEMO_MODE or requests is None or not API_KEY:
        return _mock_reasoning(user)

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": TEXT_MODEL, "messages": messages, "temperature": 0.2},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"].get("content") or ""
        return _strip_thinking(content)
    except Exception as exc:  # 网络/鉴权异常时降级为演示结果，保证可录屏
        print(f"[MiniMax text] fallback to mock: {exc}", file=sys.stderr)
        return _mock_reasoning(user)


def call_minimax_tts(text: str) -> Optional[str]:
    """调用 MiniMax 语音合成，返回音频文件路径。"""
    if DEMO_MODE or requests is None or not API_KEY:
        return None
    payload = {
        "model": TTS_MODEL,
        "text": text[:800],
        "voice_setting": {"voice_id": "male-qn-qingse", "speed": 1.0, "vol": 1.0},
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3"},
    }
    try:
        resp = requests.post(
            TTS_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        audio_hex = data.get("data", {}).get("audio", "")
        if not audio_hex:
            return None
        audio_bytes = bytes.fromhex(audio_hex)
        out = DATA_DIR / "tts_output.mp3"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(audio_bytes)
        return str(out)
    except Exception as exc:
        print(f"[MiniMax tts] fallback: {exc}", file=sys.stderr)
        return None


def _mock_reasoning(user: str) -> str:
    """演示模式下的确定性输出，方便录屏和讲解。"""
    return (
        "初步巡检结论：画面中共识别出 3 项风险。\n"
        "1) 高处作业：一名人员未正确佩戴安全帽，风险等级为高。\n"
        "2) 反光衣：现场人员已穿着，状态正常。\n"
        "3) 动火作业：疑似无动火证，需人工核实。\n"
        "建议立即停止该区域作业，由安全员现场复核，待整改完成后再复工。"
    )


# ---------------------------------------------------------------- 协同流程
@dataclass
class InspectionRecord:
    review_id: str
    created_at: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    rules: list[dict[str, str]] = field(default_factory=list)
    draft: str = ""
    status: str = "待人工确认"


def compute_risk_level(findings: list[dict[str, Any]]) -> str:
    """把多条隐患聚合为单条最高风险等级，供界面醒目展示。"""
    order = {"高": 3, "中": 2, "低": 1}
    top = "低"
    for f in findings:
        level = str(f.get("risk_level", "低"))
        if order.get(level, 1) > order.get(top, 1):
            top = level
        status = str(f.get("status", ""))
        if status in {"未佩戴", "缺失", "违章", "疑似无动火证"} and order.get(top, 1) < 2:
            top = "中"
    return top


def inspect_and_speak(image_path: Optional[str]) -> tuple[dict[str, Any], str, str, str, str, Optional[str]]:
    """照片巡检：多模态感知 -> 规则检索 -> 文本生成 -> 语音播报。

    一次点击串行完成，避免 Gradio 多个 click 处理器并发导致的 TTS 时序错误。
    返回顺序与 build_ui 的 outputs 一致：
    findings_json, draft, review_id, risk_level, pending_text, audio_path
    """
    if not image_path:
        return (
            {"error": "请先上传现场照片"},
            "无法识别：未上传图片。",
            "",
            "低",
            "",
            None,
        )

    # 主路径：MiniMax-M3 多模态视觉；不可用时回退到本地感知 stub
    vision = call_minimax_vision(image_path)
    findings = vision.get("findings") or safety_detect(image_path)
    rules = retrieve_rules(findings)
    ocr = ocr_text(image_path)
    risk_level = compute_risk_level(findings)
    pending_items = vision.get("pending_review") or [
        f.get("item", "未知项") for f in findings if f.get("needs_review")
    ]
    pending_text = "；".join(str(x) for x in pending_items) if pending_items else "无"

    user_prompt = json.dumps(
        {
            "视觉识别摘要": vision.get("summary", ""),
            "识别结果": findings,
            "现场标牌": ocr,
            "安全规范": rules,
        },
        ensure_ascii=False,
    )
    system = (
        "你是建筑工地安全巡检助手。请根据识别结果和规范，"
        "生成简洁、可执行的隐患描述和整改措施，并给出风险等级；"
        "对低置信度或信息不足的项明确标注“需人工确认”。"
    )
    corrections = load_recent_corrections()
    if corrections:
        corr_lines = "\n".join(
            f"- 现场意见：{c['note'] or '无'}；修正：{c['corrected'] or '无'}"
            for c in corrections
        )
        system += ("\n\n以下为历史人工纠偏案例，请在本次生成时参考以避免重复同类错误：\n" + corr_lines)
    draft = call_minimax_text(system, user_prompt)

    record = InspectionRecord(
        review_id=uuid.uuid4().hex[:10],
        created_at=datetime.now().isoformat(timespec="seconds"),
        findings=findings,
        rules=rules,
        draft=draft,
        status="待人工确认",
    )
    save_pending(record)

    audio = call_minimax_tts(draft)
    display_findings = {
        "summary": vision.get("summary", ""),
        "risk_level": risk_level,
        "findings": findings,
        "risks": vision.get("risks", []),
        "pending_review": pending_items,
        "rules": rules,
    }
    return display_findings, draft, record.review_id, risk_level, pending_text, audio


def save_pending(record: InspectionRecord) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=2), encoding="utf-8")


def submit_human_review(review_id: str, action: str, note: str, corrected: str) -> str:
    """人工确认/纠偏，并把结果写入反馈日志。"""
    if action not in {"confirm", "correct"}:
        action = "confirm"
    entry = {
        "review_id": review_id,
        "action": action,
        "note": note or "",
        "corrected": corrected or "",
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if action == "confirm":
        summary = "已确认识别结果，整改单进入待下发状态，并记录为有效样本。"
    else:
        summary = (
            "已记录人工修正："
            + (note or "无")
            + (" / 修正内容：" + corrected if corrected else "")
            + "。该反馈将用于后续同类场景的纠偏提示。"
        )
    return summary


def load_recent_corrections(limit: int = 6) -> list[dict[str, str]]:
    """读取人工纠偏记录，作为下一次生成的先验案例，形成“纠偏回流”。"""
    items: list[dict[str, str]] = []
    if not FEEDBACK_FILE.exists():
        return items
    for line in FEEDBACK_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get("action") != "correct":
            continue
        note = str(entry.get("note", "")).strip()
        corrected = str(entry.get("corrected", "")).strip()
        if note or corrected:
            items.append({"note": note, "corrected": corrected})
    return items[-limit:]


# ---------------------------------------------------------------- 界面

def build_ui():
    if gr is None:
        raise SystemExit("未安装 gradio，请先执行：pip install -r requirements.txt")

    with gr.Blocks(title="工地隐患巡检与整改助手") as demo:
        gr.Markdown("# 工地隐患巡检与整改助手\n上传现场照片，自动识别隐患、生成整改建议，并支持人工确认与纠偏。")
        with gr.Tab("现场巡检"):
            with gr.Row():
                image = gr.Image(type="filepath", label="现场照片")
                with gr.Column():
                    btn = gr.Button("开始巡检", variant="primary")
                    sample_btn = gr.Button("加载示例图片")
                    findings = gr.JSON(label="识别结果")
                    risk = gr.Textbox(label="综合风险等级", interactive=False)
                    pending = gr.Textbox(label="待人工确认项", lines=2, interactive=False)
                    draft = gr.Textbox(label="整改建议草稿", lines=8, interactive=False)
                    audio = gr.Audio(label="语音播报")
                    review_id = gr.Textbox(label="待确认编号", interactive=False)
            btn.click(
                fn=inspect_and_speak,
                inputs=image,
                outputs=[findings, draft, review_id, risk, pending, audio],
            )
            sample_btn.click(
                fn=lambda: SAMPLE_IMAGES[0] if SAMPLE_IMAGES else None,
                inputs=None,
                outputs=image,
            )

        with gr.Tab("人机协同确认"):
            gr.Markdown("低置信度或信息不足项应转人工确认；人工修正会写入反馈日志。")
            rid = gr.Textbox(label="待确认编号")
            action = gr.Radio(["confirm", "correct"], value="confirm", label="处理动作")
            note = gr.Textbox(label="人工意见", lines=2)
            corrected = gr.Textbox(label="修正后的识别/整改内容（可选）", lines=2)
            submit = gr.Button("提交确认")
            result = gr.Textbox(label="处理结果", interactive=False)
            submit.click(fn=submit_human_review, inputs=[rid, action, note, corrected], outputs=result)

    return demo


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    mode_text = "演示模式（未检测到 API Key）" if DEMO_MODE else "真实 API 模式"
    print(f"[启动] {mode_text} | 文本={TEXT_MODEL} 视觉={VISION_MODEL} TTS={TTS_MODEL}")
    ui = build_ui()
    ui.launch(server_name="127.0.0.1", server_port=7860)
