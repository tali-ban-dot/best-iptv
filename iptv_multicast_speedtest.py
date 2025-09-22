import requests
import chardet
import re
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import urllib.parse

IPTV_URL = "http://gm.scvip.net.cn/iptv/iptv.txt"
INPUT_FILE = "iptv.m3u"
OUTPUT_FILE = "best_multicast.txt"
TIMEOUT = 1
MAX_WORKERS = 50

GROUPS = {
    "📺央视频道": ["CCTV", "央视"],
    "📡卫视频道": ["卫视", "湖南", "北京", "东方", "山东", "四川"],
    "🌊港·澳·台": ["香港", "港", "澳门", "台湾"]
}

def download_m3u():
    """下载 IPTV 源并保持原始字节"""
    r = requests.get(IPTV_URL, timeout=10)
    with open(INPUT_FILE, "wb") as f:
        f.write(r.content)
    print(f"✅ IPTV 下载成功 ({len(r.content)} bytes)")

def parse_m3u(file_path):
    """解析 m3u/txt 文件，保持尾巴原始字节"""
    entries = []
    with open(file_path, "rb") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        i = 0
        while i < len(lines):
            line = lines[i]
            if b"#EXTINF" in line:
                # 尝试检测编码
                encoding = chardet.detect(line)['encoding'] or 'utf-8'
                try:
                    match = re.search(b',(.+)', line)
                    name_bytes = match.group(1) if match else b"Unknown"
                    name = name_bytes.decode(encoding, errors='ignore')
                except:
                    name = "Unknown"
                i += 1
                url = lines[i].decode('utf-8', errors='ignore') if i < len(lines) else ""
                entries.append((name, url))
            elif b"," in line and not line.startswith(b"#"):
                parts = line.split(b",", 1)
                if len(parts) == 2:
                    try:
                        name = parts[0].decode('utf-8', errors='ignore')
                        url = parts[1].decode('utf-8', errors='ignore')
                    except:
                        name = "Unknown"
                        url = ""
                    entries.append((name, url))
            i += 1
    print(f"📌 解析 {len(entries)} 条 IPTV 条目")
    return entries

def assign_group(name):
    for group_name, keywords in GROUPS.items():
        for kw in keywords:
            if kw.lower() in name.lower():
                return group_name
    return None

def check_latency(url, timeout=TIMEOUT):
    """简单 TCP 测速"""
    try:
        host_port = re.findall(r'://([^/:]+):?(\d*)', url)
        if not host_port:
            return float('inf')
        host, port = host_port[0]
        port = int(port) if port else 80
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            start = datetime.now()
            s.connect((host, port))
            end = datetime.now()
            latency = (end - start).total_seconds() * 1000
            return latency
    except:
        return float('inf')

def speedtest_entries(entries):
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_entry = {executor.submit(check_latency, url): (name, url) for name, url in entries}
        for future in future_to_entry:
            name, url = future_to_entry[future]
            latency = future.result()
            results.append((name, url, latency))
    return results

def main():
    download_m3u()
    all_entries = parse_m3u(INPUT_FILE)

    # 分组收集
    group_dict = {k: [] for k in GROUPS}
    for name, url in all_entries:
        group = assign_group(name)
        if group:
            group_dict[group].append((name, url))

    lines_out = [f"# IPTV 最优组播列表 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"]

    # 每组测速排序
    for group_name, entries in group_dict.items():
        if not entries:
            continue
        lines_out.append(f"\n# {group_name}\n")
        tested = speedtest_entries(entries)
        tested.sort(key=lambda x: x[2])
        for name, url, latency in tested:
            # 尾巴原样保留
            lines_out.append(f"{name},{url}")

    with open(OUTPUT_FILE, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines_out))

    print(f"✅ 已生成 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
