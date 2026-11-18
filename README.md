# 知己 · 个人知识管家

知己是一款在电脑本地运行的笔记和附件管理工具。它支持日历笔记、自定义模板、附件预览、回收站，以及 Word、Excel 等导出格式。

## Windows 上使用

1. 安装 [Python 3.13](https://www.python.org/downloads/windows/)（启用 Python Launcher）和 [Node.js 24](https://nodejs.org/en/download)。
2. 下载仓库 ZIP 并完整解压到一个自己有写入权限的文件夹，也可以用 Git 克隆仓库。
3. 双击 `Start-Zhiji.cmd`。脚本会联网安装依赖并构建前端。
4. 看到服务启动后，在浏览器打开 [知己](http://127.0.0.1:18766/)，按提示设置自己的登录密码。使用期间保留启动窗口，退出时按 Ctrl+C。

## 数据与更新

笔记、登录设置和默认附件目录都保存在自己电脑上的 `preview-backend/data`。附件位置可在知己设置里修改。更新前可通过「设置」下载完整备份；如果用 Git 克隆，拉取新版本后重新运行启动脚本。使用 ZIP 更新时，请先备份数据，并保留旧版本的数据目录，便于按备份中的说明恢复。

## 开发验证

前端在 `frontend` 中运行 `npm ci`、`npm run build` 和 `node --test tests/*.test.mjs`。后端在 `preview-backend` 中安装 `requirements.txt` 后运行 `python -m unittest test_attachments test_batch_organize`。

## 许可证

本项目使用 [MIT 许可证](LICENSE)。
