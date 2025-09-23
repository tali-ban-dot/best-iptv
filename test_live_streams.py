import requests
import subprocess
import json
from pathlib import Path

# ===== 配置 =====
M3U_URL = "https://raw.githubusercontent.com/YanG-1989/m3u/refs/heads/main/Migu.m3u"
M3U_FILE = "valid_streams.m3u"
TXT_FILE = "valid_streams.txt"
REPORT_FILE = "test_report.json"

# ffmpeg 测试时间（秒）
TEST_DURATION = 10

def check_stream(url: str, timeout: int = TEST_DURATION) -> bool:
    """用 ffmpeg 测试流是否可用"""
    try:
        cmd = ["ffmpeg", "-v", "error", "-i", url, "-t", str(timeout), "-f", "null", "-"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout+5)
        return result.returncode == 0
    except Exception:
        return False

def main():
    # 抓取 M3U
    try:
        resp = requests.get(M3U_URL, timeout=15)
        resp.raise_for_status()
        lines = resp.text.splitlines()
    except Exception as e:
        print(f"❌ 抓取 M3U 失败: {e}")
        return

    # 解析 M3U
    streams = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            name = line.split(",", 1)[1].strip() if "," in line else "未知频道"
            if i + 1 < len(lines) and lines[i+1].startswith("http"):
                url = lines[i+1].strip()
                streams.append({"name": name, "url": url})
                i += 1
        i += 1

    # 检测有效源
    valid_streams = []
    report = []
    for s in streams:
        ok = check_stream(s["url"], timeout=TEST_DURATION)
        report.append({"name": s["name"], "url": s["url"], "valid": ok})
        if ok:
            valid_streams.append(s)
            print(f"✅ 有效: {s['name']} -> {s['url']}")
        else:
            print(f"❌ 无效: {s['name']} -> {s['url']}")

    # 写入 m3u
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for s in valid_streams:
            f.write(f"#EXTINF:-1,{s['name']}\n{s['url']}\n")

    # 写入 txt
    with open(TXT_FILE, "w", encoding="utf-8") as f:
        for s in valid_streams:
            f.write(f"{s['name']},{s['url']}\n")

    # 写入报告
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
