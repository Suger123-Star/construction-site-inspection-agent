# 部署到 Hugging Face Spaces（获得公网智能体链接）

## 方式一：网页创建 Space
1. 登录 https://huggingface.co
2. 新建 Space，SDK 选 `Gradio`，硬件选 `CPU Basic`（免费）。
3. 把本目录的 `app.py`、`requirements.txt`、`.env.example`、`README.md` 上传到 Space 仓库。
4. 在 Space 的 Settings → Secrets 中添加 `MINIMAX_API_KEY`。
5. 等待构建完成后，复制 Space 的 `https://<用户名>-<空间名>.hf.space` 链接，作为“智能体链接”提交。

## 方式二：git 推送
```bash
git clone https://huggingface.co/spaces/<用户名>/<空间名>
cd <空间名>
# 复制 app.py、requirements.txt、README.md、.env.example 到这里
git add .
git commit -m "submission"
git push
```

## 提示
- 如不配置 `MINIMAX_API_KEY`，Space 会自动进入演示模式，仍可正常打开界面并输出演示结果。
- 如官方报名系统要求填写“智能体链接”，优先提交 Spaces 链接；如只接受代码包，提交 `工地隐患巡检与整改助手-代码包.zip`。
