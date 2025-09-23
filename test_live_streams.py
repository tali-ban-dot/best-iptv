import requests
import subprocess
import concurrent.futures
import os

# ===== 配置 =====
m3u_url = "https://raw.githubusercontent.com/YanG-1989/m3u/refs/heads/main/Migu.m3u"
timeout_requests = 10   # HTTP请求超时
timeout_ffmpeg = 10     # ffmpeg拉流超时
max_threads_http = 10
max_threads_ffmpeg = 5

output_m3u = "valid_streams.m3u"
output_txt = "valid_streams.txt"

# ===== 解析 M3U =====
def parse_m3u(content):
    lines = content.splitlines()
    streams = []
    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF"):
            name = lines[i].split(",", 1)[-1].strip()
            url = lines[i+1].strip() if i+1 < len(lines) else ""
            streams.append({"name": name, "url": url})
    return streams

# ===== HTTP 快速检测 =====
def check_http(stream):
    try:
        r = requests.head(stream["url"], timeout=timeout_requests, allow_redirects=True)
        if r.status_code == 200:
            return stream
    except:
        pass
    return None

# ===== ffmpeg 拉流检测 =====
def check_ffmpeg(stream):
    try:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "quiet",
            "-i", stream["url"],
            "-t", str(timeout_ffmpeg), "-f", "null", "-"
        ]
        subprocess.run(cmd, timeout=timeout_ffmpeg + 5, check=True)
        print(f"✅ 有效: {stream['name']} -> {stream['url']}")
        return stream
    except:
        print(f"❌ 无效: {stream['name']} -> {stream['url']}")
        return None

def main():
    # 拉取 M3U
    r = requests.get(m3u_url, timeout=timeout_requests)
    streams = parse_m3u(r.text)
    print(f"解析到 {len(streams)} 个直播源")

    # HTTP快速筛选
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads_http) as executor:
        results = list(executor.map(check_http, streams))
    streams_http_ok = [s for s in results if s]
    print(f"HTTP检测通过 {len(streams_http_ok)} 个直播源")

    # ffmpeg 拉流验证
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads_ffmpeg) as executor:
        results = list(executor.map(check_ffmpeg, streams_http_ok))
    valid_streams = [s for s in results if s]
    print(f"最终有效直播源 {len(valid_streams)} 个")

    # 输出 M3U
    with open(output_m3u, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for s in valid_streams:
            f.write(f"#EXTINF:-1,{s['name']}\n{s['url']}\n")

    # 输出 TXT
    with open(output_txt, "w", encoding="utf-8") as f:
        for s in valid_streams:
            f.write(f"{s['name']},{s['url']}\n")

    print(f"已生成 {output_m3u} 和 {output_txt}")

if __name__ == "__main__":
    main()
