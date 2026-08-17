# Video AI Demo

免费小规模演示：GitHub Pages 提供固定前端地址，当前电脑通过临时公网隧道提供视频分析 API。

当前分析功能读取 MP4/MOV/M4V 文件中的 `mvhd` 元数据并返回视频时长。上传数据仅保存在内存中，响应结束后即释放。

## 启动

本机需要 Python 3、Git、OpenSSH 和 `nc`。Git 仓库需要具有 GitHub 推送权限。

```bash
python3 start_demo.py
```

如果所在网络禁止 `git push`，使用手动模式：

```bash
python3 start_demo.py --manual
```

脚本会自动打印包含 `?api=` 参数的完整 GitHub Pages 分享链接，不修改仓库文件，也不会执行 `git push`。把该链接直接发给用户即可。

启动脚本会：

1. 在 `127.0.0.1:8765` 启动分析后端。
2. 通过 `127.0.0.1:6789` HTTP 代理建立 localhost.run 隧道。
3. 打印带有后端地址参数的 GitHub Pages 分享链接。
4. 非手动模式下，仍可选择自动更新 `backend-url.json`。

停止脚本后隧道立即失效。再次启动时会获取新地址并自动更新页面。
