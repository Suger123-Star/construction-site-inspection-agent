# 工地隐患巡检与整改助手

## 一句话介绍
面向建筑工地的“拍照巡检 + AI整改单 + 人工纠偏”智能体：上传现场照片，自动识别安全帽/反光衣/动火作业等隐患，调用 MiniMax 生成整改建议和语音播报；低置信度项转人工确认，人工反馈回写形成纠偏闭环。

## 为什么这样选题
- 紧扣赛事主题：`为人民建好房，为工友谋幸福`。
- 命中三个评审维度：
  - 场景创意价值：真实工地隐患巡检，落地明确。
  - AI协同能力：`感知模型 -> MiniMax推理 -> 人工确认 -> 反馈回写` 的人机协同闭环。
  - 技术创新能力：多模型整合 + 规则/知识检索 + 低置信度自动转人工。

## 技术架构
```
现场照片/语音
   │
  ├─ 多模态视觉：MiniMax-M3 识别安全帽/反光衣/动火作业等隐患（可回退 PaddleDetection）
  ├─ 标牌识别：PaddleOCR（Demo 内置模拟标牌）
  ├─ 开源语音：Whisper / FunASR 语音转写
   ▼
安全规则库（可升级为 bge-m3 + Chroma 向量检索）
   ▼
MiniMax-M3 / MiniMax-M2：视觉识别、风险描述、整改措施、纠偏总结
   ▼
MiniMax speech-2.8-turbo：语音播报
   ▼
人机确认：低置信度转人工 -> 反馈写入 feedback_log.jsonl
```

## 快速开始
1. 安装依赖：
   ```
   python -m pip install -r requirements.txt
   ```
2. 配置 MiniMax Key（详细步骤见 `MiniMaxAPI开通配置指南.md`）：
   ```
   copy .env.example .env
   # 编辑 .env，把 MINIMAX_API_KEY= 后面填成你的真实 Key
   ```
3. 验证真实调用（可选，推荐）：
   ```
   python minimax_smoke_test.py
   ```
4. 启动：
   ```
   python app.py
   ```
   浏览器打开 `http://127.0.0.1:7860`。
5. 没有 API Key 时自动进入演示模式，可直接录屏和调试。

## MiniMax API 接入状态
- 代码已接入 `MiniMax-M3`（多模态视觉）、`MiniMax-M2`（文本推理）、`speech-2.8-turbo`（语音合成）。
- 默认使用国内 OpenAI 兼容接口 `https://api.minimaxi.com/v1`。
- 配置真实 Key 后 `app.py` 自动切换为真实调用；无 Key 时进入 `DEMO_MODE` 用内置模拟结果跑通交互。
- 冒烟测试脚本：`minimax_smoke_test.py`（支持 `--text` / `--vision` / `--tts` / `--sdk`）。

## 接入真实模型
- MiniMax：按 `MiniMaxAPI开通配置指南.md` 完成注册、获取 Key、填 `.env`、跑冒烟测试。
- 安全帽/反光衣：克隆 `PaddlePaddle/PaddleDetection`，下载 helmet 预训练模型，把推理结果填到 `app.py` 的 `_paddledetection_detect()`。
- OCR：`pip install paddleocr`，在 `ocr_text()` 中调用。
- ASR：`pip install openai-whisper` 或 `funasr`，在 `transcribe_audio()` 中调用。
- 向量检索：把 `retrieve_rules()` 替换为 `bge-m3 + chromadb`。

## 提交材料映射
| 提交项 | 对应文件 |
|---|---|
| 智能体链接 | 本地 `http://127.0.0.1:7860`，或部署到 Hugging Face Spaces / 云服务器后的公网链接 |
| 代码包 | 本目录（含 README、app.py、requirements、.env.example），建议打包为 ZIP |
| 技术说明 | `项目技术说明文档.pdf`（6 页，可直接提交） |
| 演示视频 | `核心功能介绍视频.mp4`（1 分 28 秒，1080P，含旁白） |
| 履历表 | `人机协同履历表.docx`（把【】占位替换为真实成员信息） |
| 补充材料 | `补充资料.zip`（创意故事板、提示词日志、演示素材） |

## 许可说明
- 本项目代码仅为参赛演示集成；MiniMax 为商业 API，需遵守其平台条款。
- 如使用 PaddleDetection/PaddleOCR/Whisper 等开源模型，提交时请保留其 License 声明。
- 建议优先使用 Apache-2.0 / MIT 组件；AGPL 组件若以网络服务形式提供需谨慎。