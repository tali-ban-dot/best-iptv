import concurrent.futures
import subprocess
import re
from datetime import datetime
import requests

# IPTV 源文件 URL 或仓库内文件
IPTV_URL = "https://raw.githubusercontent.com/tali-ban-dot/best-iptv/main/iptv.m3u"
INPUT_FILE = "iptv.m3u"
OUTPUT_FILE = "best_multicast.txt"
TIMEOUT = 3  # 秒

# 节目分组规则
GROUPS = {
    "📺央视频道": ["CCTV", "央视"],
    "📡卫视频道": ["卫视", "湖南", "北京", "东方", "山东", "四川"],
    "🌊港·澳·台": ["香港", "港", "澳门", "台湾"]
}

def download_m3u():
    try:
        r = requests.get(IPTV_URL, timeout=10)
        with open(INPUT_FILE, "w", encoding="utf-8") as f:
            f.write(r.text)
        print(f"✅ IPTV m3u 下载成功: {INPUT_FILE}")
    except Exception as e:
        print(f"❌ IPTV 下载失败: {e}")

def ping_url(url):
    """测试 URL 延迟"""
    try:
        host = re.findall(r'://([^/:]+)', url)[0]
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(TIMEOUT), host],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        match = re.search(r'time=([\d.]+) ms', result.stdout)
        return float(match.group(1)) if match else float('inf')
    except:
        return float('inf')

def parse_m3u(file_path):
    """解析 m3u 返回 [(节目名, URL)]"""
    entries = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [line.strip() for line in f if line.strip()]
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("#EXTINF"):
                match = re.search(r',(.+)', line)
                name = match.group(1).strip() if match else f"Unknown{i}"
                i += 1
                url = lines[i] if i < len(lines) else ""
                entries.append((name, url))
            i += 1
    return entries

def assign_group(name):
    for group_name, keywords in GROUPS.items():
        for kw in keywords:
            if kw in name:
                return group_name
    return None

def speedtest_entries(entries):
    """对每个直播源测速"""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_entry = {executor.submit(ping_url, url): (name, url) for name, url in entries}
        for future in concurrent.futures.as_completed(future_to_entry):
            name, url = future_to_entry[future]
            latency = future.result()
            results.append((name, url, latency))
    return results

def main():
    # 下载最新 IPTV 文件
    download_m3u()

    all_entries = parse_m3u(INPUT_FILE)
    group_dict = {k: [] for k in GROUPS.keys()}

    # 按分组收集
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
        for name, url, _ in tested:
            lines_out.append(f"{name},{url}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out))

    print(f"✅ 已生成 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
