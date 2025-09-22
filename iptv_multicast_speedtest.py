import concurrent.futures
import subprocess
import re
from datetime import datetime
import requests
import chardet
import os

# IPTV 源文件 URL 或仓库内文件
IPTV_URL = "http://gm.scvip.net.cn/iptv/iptv.txt"  # 可替换为你的源
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
    """下载 IPTV m3u/txt 文件"""
    try:
        r = requests.get(IPTV_URL, timeout=10)
        r.encoding = 'utf-8'  # 尝试 utf-8
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
    return "未分组"

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
    download_m3u()
    all_entries = parse_m3u(INPUT_FILE)

    # 按分组收集
    group_dict = {}
    for name, url in all_entries:
        group = assign_group(name)
        if group not in group_dict:
            group_dict[group] = []
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

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out))

    print(f"✅ 已生成 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
