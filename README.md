# Video AI Demo

免费小规模演示：GitHub Pages 提供固定前端地址，当前电脑通过临时公网隧道提供视频分析 API。

当前分析功能读取 MP4/MOV/M4V 文件中的 `mvhd` 元数据并返回视频时长。上传数据仅保存在内存中，响应结束后即释放。

## 启动

本机需要 Python 3、Git、OpenSSH 和 `nc`。Git 仓库需要具有 GitHub 推送权限。

```bash
python3 start_demo.py
```

启动脚本会：

1. 在 `127.0.0.1:8765` 启动分析后端。
2. 通过 `127.0.0.1:6789` HTTP 代理建立 localhost.run 隧道。
3. 将新隧道地址写入 `backend-url.json`。
4. 自动提交并推送配置，使 GitHub Pages 页面连接到新后端。

停止脚本后隧道立即失效。再次启动时会获取新地址并自动更新页面。
