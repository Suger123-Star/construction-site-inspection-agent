# MiniMax API 开通与配置指南（工地隐患巡检与整改助手）

本指南面向本项目 `C-工地隐患巡检与整改助手`，说明如何开通 MiniMax 开放平台账号、获取 API Key，并把 Key 配置到本地，使程序从“演示模式”切换到“真实模型调用”。

> 诚实说明：项目代码已经完成 MiniMax 接口接入，但**目前没有你的 API Key**，所以本地运行走的是 `DEMO_MODE`（内置模拟结果）。下面的步骤全部完成后，`app.py` 会自动切换到真实的 MiniMax-M3 视觉、MiniMax-M2 文本和 `speech-2.8-turbo` 语音。

---

## 1. 注册 / 登录 MiniMax 开放平台

1. 打开国内官网：<https://platform.minimaxi.com>
2. 点击右上角“注册 / 登录”，用手机号或邮箱注册并完成验证。
3. 注册入口（备用）：<https://platform.minimaxi.com>，海外用户使用 <https://platform.minimax.io>。

> 我不建议、也不会替你注册账号。注册需要你的手机号 / 邮箱验证码和实名信息，这一步只能由你本人完成。

## 2. 完成实名认证（按需）

- 首次调用模型前，平台通常要求完成**个人实名认证**（姓名 + 身份证 / 手机号）。
- 若需要企业发票或更高额度，可做**企业认证**。
- 路径：登录后进入 **账户管理 → 实名认证**。

## 3. 获取 API Key

1. 登录后进入 **账户管理 → 接口密钥（API Keys）**。
2. 点击 **创建 API Key**（或“新建密钥”）。
3. 命名建议：`工地巡检助手-本地测试`。
4. 创建后**立即复制保存**，形如：
   ```
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...（示例，不是真实 Key）
   ```
   实际 Key 通常以 `sk-` 或平台返回格式为准。

> 安全提醒：API Key 等同于账户密码，不要发到群聊、不要提交到 Git、不要贴给任何人。

## 4. 把 Key 配置到项目

项目根目录已提供 `.env.example`。请复制为 `.env` 并填入真实 Key。

### 方式 A：写入 `.env`（推荐，仅本项目生效）

在项目目录 `outputs/C-工地隐患巡检与整改助手` 下，复制并填写：

```dotenv
MINIMAX_API_KEY=你的真实APIKey
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_TEXT_MODEL=MiniMax-M2
MINIMAX_VISION_MODEL=MiniMax-M3
MINIMAX_TTS_MODEL=speech-2.8-turbo
MINIMAX_TTS_URL=https://api.minimaxi.com/v1/t2a_v2
DEMO_MODE=auto
```

PowerShell 快捷命令（在项目目录执行）：

```powershell
Copy-Item .env.example .env
notepad .env
```

把 `MINIMAX_API_KEY=sk-xxxxxxxxxxxxxxxx` 这一行改成你的真实 Key，保存。

### 方式 B：写入 Windows 用户环境变量（全局生效，可选）

```powershell
[Environment]::SetEnvironmentVariable("MINIMAX_API_KEY", "你的真实APIKey", "User")
[Environment]::SetEnvironmentVariable("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1", "User")
```

设置后需**重开终端**（或重启 IDE）才能生效。

## 5. 安装依赖

项目虚拟环境已位于 `work/venv`。核心依赖和官方 OpenAI SDK：

```powershell
# 在项目根目录 wo\ 下
.\work\venv\Scripts\python.exe -m pip install -r "outputs\C-工地隐患巡检与整改助手\requirements.txt"
```

`requirements.txt` 已包含 `gradio`、`requests`、`python-dotenv`、`openai`。

## 6. 运行冒烟测试

```powershell
cd "outputs\C-工地隐患巡检与整改助手"
..\..\work\venv\Scripts\python.exe minimax_smoke_test.py
```

预期输出应包含：

```text
[1/3] 文本模型 MiniMax-M2  OK: ...
[2/3] 视觉模型 MiniMax-M3  OK: ...
[3/3] 语音合成 speech-2.8-turbo  OK: 已保存 ... tts_smoke.mp3
结果: 全部通过 ✔
```

如果只想测单项：

```powershell
..\..\work\venv\Scripts\python.exe minimax_smoke_test.py --text
..\..\work\venv\Scripts\python.exe minimax_smoke_test.py --vision
..\..\work\venv\Scripts\python.exe minimax_smoke_test.py --tts
..\..\work\venv\Scripts\python.exe minimax_smoke_test.py --sdk   # 用官方 OpenAI SDK 验证
..\..\work\venv\Scripts\python.exe minimax_smoke_test.py --anthropic   # 用官方 Anthropic SDK 验证
```

## 7. 启动应用（真实调用）

```powershell
cd "outputs\C-工地隐患巡检与整改助手"
..\..\work\venv\Scripts\python.exe app.py
```

浏览器打开 <http://127.0.0.1:7860>，上传工地现场照片后点击“识别并播报”，此时会走真实模型。终端如出现 `[MiniMax vision/text/tts] fallback`，说明调用失败，请按第 9 节排查。

## 补充：Anthropic 兼容接口（可选）

MiniMax 还提供 Anthropic API 兼容接口，适合已使用 Claude/Anthropic 生态的开发者。本项目 `app.py` 默认走 OpenAI 兼容 + `requests`，冒烟测试额外支持 `--anthropic` 验证这条链路。

```dotenv
MINIMAX_ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
```

```python
import anthropic
client = anthropic.Anthropic(
    api_key="你的Key",
    base_url="https://api.minimaxi.com/anthropic",
)
resp = client.messages.create(
    model="MiniMax-M3",
    max_tokens=1000,
    messages=[{"role": "user", "content": "你好"}],
)
```

注意：
- Anthropic 兼容接口下，`MiniMax-M3` 默认**关闭** thinking；如需开启，传 `thinking={"type": "adaptive"}`。
- `MiniMax-M3` 支持图片/视频输入（`type="image"` 内容块）；`MiniMax-M2` 系列只支持文本和工具调用。
- 语音合成仍需走 T2A v2 接口（`/v1/t2a_v2`），Anthropic 接口不含 TTS。

## 8. 计费与额度

- 文本 / 视觉走 **Token Plan 或按量计费**：`MiniMax-M3` 多模态输入图片会消耗图片 token，`MiniMax-M2` 文本按 token 计费。
- 语音 `speech-2.8-turbo` 走 **语音资源包**（T2A v2 接口），一般需要先购买/领取语音资源包，否则可能报余额或权限错误。
- 新账号通常有少量免费体验额度，足够完成比赛录屏和演示；但具体以平台页面为准：
  - 定价总览：<https://platform.minimaxi.com/docs/pricing/overview.md>
  - 语音资源包：<https://platform.minimaxi.com/docs/guides/pricing-speech.md>

## 9. 常见错误排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| `401 Unauthorized` | Key 错误或未填入 | 检查 `.env` 中 Key，注意不要有多余空格/引号 |
| `403 Forbidden` | 未实名 / 无对应模型权限 | 完成实名认证，检查 Token Plan 或资源包 |
| `404 Not Found` | base_url 或路径错误 | 保持 `https://api.minimaxi.com/v1`，TTS 用 `/v1/t2a_v2` |
| `429 Too Many Requests` | 触发速率限制 | 稍后重试，降低并发 |
| TTS 返回空 audio 或余额错误 | 无语音资源包 | 购买/领取语音资源包，或用文本+视觉先演示 |
| 终端中文乱码 | 控制台代码页为 GBK | 执行 `chcp 65001` 或 `$env:PYTHONUTF8=1` 后重试 |

## 10. 安全与提交提醒

- `.env` 已加入代码包但不含真实 Key，提交官网的代码包**请确保只包含 `.env.example`**，不要打包你本地的 `.env`。
- 不要在演示视频、技术文档、提交材料中暴露真实 API Key。
- 官网提交前，先跑一次冒烟测试确认三路调用都通过，再重新录屏，即可在文档中写“已真实调用 MiniMax-M3 / MiniMax-M2 / speech-2.8-turbo”。