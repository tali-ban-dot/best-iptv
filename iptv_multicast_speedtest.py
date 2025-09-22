import concurrent.futures
import subprocess
import re
from datetime import datetime

INPUT_FILE = "iptv.m3u"  # 你的 m3u 文件
OUTPUT_FILE = "best_multicast.txt"
TIMEOUT = 3  # 秒

# 节目分组规则（关键字匹配）
GROUPS = {
    "📺央视频道": ["CCTV", "央视"],
    "📡卫视频道": ["卫视", "湖南", "北京", "东方", "山东", "四川"],
    "🌊港·澳·台": ["香港", "港", "澳门", "台湾"]
}

def ping_url(url):
    """测试 URL 延迟，返回毫秒"""
    try:
        host = re.findall(r'://([^/:]+)', url)[0]
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(TIMEOUT), host],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        match = re.search(r'time=([\d.]+) ms', result.stdout)
        if match:
            return float(match.group(1))
        else:
            return float('inf')
    except Exception:
        return float('inf')

def parse_m3u(file_path):
    """解析 m3u 文件，返回 [(节目名, URL)]"""
    entries = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [line.strip() for line in f if line.strip()]
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("#EXTINF"):
                # 获取节目名
                match = re.search(r',(.+)', line)
                name = match.group(1).strip() if match else f"Unknown{i}"
                # 下一行是 URL
                i += 1
                url = lines[i] if i < len(lines) else ""
                entries.append((name, url))
            i += 1
    return entries

def assign_group(name):
    """根据节目名分组"""
    for group_name, keywords in GROUPS.items():
        for kw in keywords:
            if kw in name:
                return group_name
    return None  # 不分组

def speedtest_lines(lines):
    """对每组进行测速"""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_line = {executor.submit(ping_url, url): (name, url) for name, url in lines}
        for future in concurrent.futures.as_completed(future_to_line):
            name, url = future_to_line[future]
            latency = future.result()
            results.append((name, url, latency))
    # 按延迟排序
    results.sort(key=lambda x: x[2])
    return results

def main():
    all_entries = parse_m3u(INPUT_FILE)

    group_dict = {k: [] for k in GROUPS.keys()}
    for name, url in all_entries:
        group = assign_group(name)
        if group:
            group_dict[group].append((name, url))

    lines_out = [f"# IPTV 最优组播列表 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"]

    for group_name, entries in group_dict.items():
        if not entries:
            continue
        lines_out.append(f"\n# {group_name}\n")
        best_entries = speedtest_lines(entries)
        for name, url, _ in best_entries:
            lines_out.append(f"{name},{url}")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines_out))

    print(f"✅ 已生成 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
