import concurrent.futures
import re
from datetime import datetime
import requests
import chardet
import os
import socket

# IPTV 源文件 URL
IPTV_URL = "http://gm.scvip.net.cn/iptv/iptv.txt"  # 可替换为你的源
INPUT_FILE = "iptv.m3u"
OUTPUT_FILE = "best_multicast.txt"
TIMEOUT = 1          # ping/连接超时 1 秒
MAX_WORKERS = 50     # 并发线程数

# 节目分组规则
GROUPS = {
    "📺央视频道": ["CCTV", "央视"],
    "📡卫视频道": ["卫视", "湖南", "北京", "东方", "山东", "四川"],
    "🌊港·澳·台": ["香港", "港", "澳门", "台湾"]
}

def download_m3u():
    """下载 IPTV m3u/txt 文件"""
    try:
        r = requests.get(IPTV_URL, timeout=10)
        r.encoding = 'utf-8'  # 尝试 UTF-8
        with open(INPUT_FILE, "w", encoding="utf-8") as f:
            f.write(r.text)
        print(f"✅ IPTV 下载成功: {INPUT_FILE}")
    except Exception as e:
        print(f"❌ IPTV 下载失败: {e}")
        if not os.path.exists(INPUT_FILE):
            raise RuntimeError("无法获取 IPTV 文件")

def parse_m3u(file_path):
    """解析 m3u/txt 文件，返回 [(节目名, URL)]"""
    # 检测文件编码
    with open(file_path, 'rb') as f:
        rawdata = f.read()
        result = chardet.detect(rawdata)
        encoding = result['encoding'] if result['encoding'] else 'utf-8'

    entries = []
    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
        lines = [line.strip() for line in f if line.strip()]
        i = 0
        while i < len(lines):
            line = lines[i]
            # #EXTINF 格式
            if line.startswith("#EXTINF"):
                match = re.search(r',(.+)', line)
                name = match.group(1).strip() if match else f"Unknown{i}"
                i += 1
                url = lines[i] if i < len(lines) else ""
                entries.append((name, url))
            # 直接 CSV 格式
            elif "," in line and not line.startswith("#"):
                parts = line.split(",", 1)
                if len(parts) == 2:
                    name, url = parts
                    entries.append((name.strip(), url.strip()))
            i += 1
    print(f"📌 解析到 {len(entries)} 条 IPTV 条目")
    return entries

def assign_group(name):
    """按节目名匹配分组"""
    for group_name, keywords in GROUPS.items():
        for kw in keywords:
            if kw.lower() in name.lower():
                return group_name
    return None  # 不匹配任何组的忽略

def check_latency(url, timeout=TIMEOUT):
    """测试直播源延迟，使用 TCP 连接代替 ping"""
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
    """对每个直播源测速"""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_entry = {executor.submit(check_latency, url): (name, url) for name, url in entries}
        for future in concurrent.futures.as_completed(future_to_entry):
            name, url = future_to_entry[future]
            latency = future.result()
            results.append((name, url, latency))
    return results

def main():
    download_m3u()
    all_entries = parse_m3u(INPUT_FILE)

    # 按分组收集，只保留三组
    group_dict = {k: [] for k in GROUPS}
    for name, url in all_entries:
        group = assign_group(name)
        if group:
            group_dict[group].append((name, url))

    lines_out = [f"# IPTV 最优组播列表 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"]

    # 每个直播源测速排序
    for group_name, entries in group_dict.items():
        if not entries:
            continue
        lines_out.append(f"\n# {group_name}\n")
        tested = speedtest_entries(entries)
        tested.sort(key=lambda x: x[2])  # 按延迟升序
        for name, url, latency in tested:
            lines_out.append(f"{name},{url}")

    # 输出文件，utf-8-sig 保证中文不乱码
    with open(OUTPUT_FILE, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines_out))

    print(f"✅ 已生成 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
