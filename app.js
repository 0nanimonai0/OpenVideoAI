const MAX_BYTES = 100 * 1024 * 1024;
let selectedFile = null;
let backendUrl = "";
let previewUrl = "";

const $ = (id) => document.getElementById(id);
const fileInput = $("videoFile");
const dropZone = $("dropZone");
const fileCard = $("fileCard");
const analyzeButton = $("analyzeButton");

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDuration(seconds) {
  const rounded = Math.max(0, Math.round(seconds));
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const secs = rounded % 60;
  return hours
    ? `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function setStatus(kind, text) {
  const el = $("serviceStatus");
  el.className = `status status-${kind}`;
  el.querySelector("span:last-child").textContent = text;
}

function showMessage(text) {
  $("message").textContent = text;
  $("message").classList.remove("hidden");
}

function clearMessage() {
  $("message").classList.add("hidden");
}

async function refreshBackend() {
  try {
    const response = await fetch(`backend-url.json?t=${Date.now()}`, { cache: "no-store" });
    const config = await response.json();
    const nextUrl = String(config.url || "").replace(/\/$/, "");
    if (!nextUrl) throw new Error("服务尚未启动");
    backendUrl = nextUrl;
    const health = await fetch(`${backendUrl}/health?t=${Date.now()}`, { cache: "no-store" });
    if (!health.ok) throw new Error("健康检查失败");
    setStatus("online", "分析服务在线");
    analyzeButton.disabled = !selectedFile;
  } catch (error) {
    backendUrl = "";
    setStatus("offline", "分析服务离线");
    analyzeButton.disabled = true;
  }
}

function useFile(file) {
  clearMessage();
  $("resultCard").classList.add("hidden");
  if (!file) return;
  const validExtension = /\.(mp4|mov|m4v)$/i.test(file.name);
  if (!validExtension) {
    showMessage("当前演示仅支持 MP4、MOV 或 M4V 视频。");
    return;
  }
  if (file.size > MAX_BYTES) {
    showMessage("视频超过 100 MB，请选择更小的文件进行演示。");
    return;
  }
  selectedFile = file;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  $("preview").src = previewUrl;
  $("fileName").textContent = file.name;
  $("fileMeta").textContent = `${formatBytes(file.size)} · 正在读取媒体信息`;
  $("preview").onloadedmetadata = () => {
    $("fileMeta").textContent = `${formatBytes(file.size)} · 本地预览 ${formatDuration($("preview").duration)}`;
  };
  dropZone.classList.add("hidden");
  fileCard.classList.remove("hidden");
  analyzeButton.disabled = !backendUrl;
}

function resetFile() {
  selectedFile = null;
  fileInput.value = "";
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = "";
  fileCard.classList.add("hidden");
  dropZone.classList.remove("hidden");
  $("resultCard").classList.add("hidden");
  $("progressWrap").classList.add("hidden");
  analyzeButton.disabled = true;
  clearMessage();
}

function analyze() {
  if (!selectedFile || !backendUrl) return;
  clearMessage();
  $("resultCard").classList.add("hidden");
  $("progressWrap").classList.remove("hidden");
  $("progressLabel").textContent = "正在上传视频";
  $("progressBar").style.width = "0%";
  $("progressValue").textContent = "0%";
  analyzeButton.disabled = true;

  const request = new XMLHttpRequest();
  request.open("POST", `${backendUrl}/api/duration`);
  request.setRequestHeader("Content-Type", selectedFile.type || "application/octet-stream");
  request.setRequestHeader("X-File-Name", encodeURIComponent(selectedFile.name));
  request.upload.onprogress = (event) => {
    if (!event.lengthComputable) return;
    const percent = Math.round((event.loaded / event.total) * 100);
    $("progressBar").style.width = `${percent}%`;
    $("progressValue").textContent = `${percent}%`;
    if (percent === 100) $("progressLabel").textContent = "正在解析视频元数据";
  };
  request.onload = () => {
    analyzeButton.disabled = false;
    try {
      const result = JSON.parse(request.responseText);
      if (request.status < 200 || request.status >= 300) throw new Error(result.error || "分析失败");
      $("durationResult").textContent = formatDuration(result.duration_seconds);
      $("resultName").textContent = result.filename;
      $("resultSeconds").textContent = `${result.duration_seconds.toFixed(3)} 秒`;
      $("resultMethod").textContent = result.method;
      $("resultCard").classList.remove("hidden");
      $("progressWrap").classList.add("hidden");
    } catch (error) {
      $("progressWrap").classList.add("hidden");
      showMessage(error.message || "无法解析服务器返回结果。");
    }
  };
  request.onerror = () => {
    analyzeButton.disabled = false;
    $("progressWrap").classList.add("hidden");
    showMessage("无法连接分析服务，临时隧道可能已经断开，请稍后重试。");
    refreshBackend();
  };
  request.send(selectedFile);
}

fileInput.addEventListener("change", () => useFile(fileInput.files[0]));
$("changeFile").addEventListener("click", resetFile);
analyzeButton.addEventListener("click", analyze);
for (const name of ["dragenter", "dragover"]) {
  dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  });
}
for (const name of ["dragleave", "drop"]) {
  dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  });
}
dropZone.addEventListener("drop", (event) => useFile(event.dataTransfer.files[0]));

refreshBackend();
setInterval(refreshBackend, 15000);
