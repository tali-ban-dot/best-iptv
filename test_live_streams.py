import subprocess
import json
from pathlib import Path

# 输入源文件
INPUT_FILE = "streams.txt"
M3U_FILE = "valid_streams.m3u"
TXT_FILE = "valid_streams.txt"
REPORT_FILE = "test_report.json"

def check_stream(url: str, timeout: int = 5) -> bool:
    """
    用 ffmpeg 测试流是否可用，超时/错误视为不可用
    """
    try:
        cmd = [
            "ffmpeg", "-v", "error",
            "-i", url,
            "-t", str(timeout),
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout+3)
        return result.returncode == 0
    except Exception:
        return False

def main():
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        print(f"❌ {INPUT_FILE} 不存在，请先添加直播源！")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        streams = [line.strip() for line in f if line.strip()]

    valid_streams = []
    report = []

    for url in streams:
        ok = check_stream(url)
        report.append({"url": url, "valid": ok})
        if ok:
            valid_streams.append(url)
            print(f"✅ 有效: {url}")
        else:
            print(f"❌ 无效: {url}")

    # 写入 m3u
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for url in valid_streams:
            f.write(f"#EXTINF:-1,{url}\n{url}\n")

    # 写入 txt
    with open(TXT_FILE, "w", encoding="utf-8") as f:
        for url in valid_streams:
            f.write(url + "\n")

    # 写入报告
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
