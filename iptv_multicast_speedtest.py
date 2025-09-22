import requests
import time
import re

# IPTV 源
iptv_url = "http://gm.scvip.net.cn/iptv/iptv.txt"

# 下载源文件
resp = requests.get(iptv_url, timeout=15)
resp.encoding = "utf-8"  # 如果乱码，可改成 gb18030
lines = resp.text.splitlines()

# 分组
groups = {
    "📺央视频道": [],
    "📡卫视频道": [],
    "🌊港·澳·台": []
}

current_group = None
for line in lines:
    line = line.strip()
    if not line:
        continue
    if line.startswith("📺央视频道"):
        current_group = "📺央视频道"
    elif line.startswith("📡卫视频道"):
        current_group = "📡卫视频道"
    elif line.startswith("🌊港·澳·台"):
        current_group = "🌊港·澳·台"
    elif line.startswith("#genre#"):
        continue
    elif current_group:
        # 只保留组播源
        if re.search(r"^(udp|rtp)://", line.split(",")[-1]):
            groups[current_group].append(line)

# 测速函数
def test_speed(url):
    try:
        start = time.time()
        r = requests.get(url, stream=True, timeout=3)
        _ = next(r.iter_content(1024))
        return time.time() - start
    except Exception:
        return 9999

# 每组保留前 N 个最快的
TOP_N = 5
best = {}

for g, items in groups.items():
    results = []
    for item in items:
        if "," in item:
            name, url = item.split(",", 1)
            t = test_speed(url)
            results.append((t, item))
    results.sort(key=lambda x: x[0])  # 按时间排序
    best[g] = [item for _, item in results[:TOP_N]]

# 写入文件
with open("best_multicast.txt", "w", encoding="utf-8") as f:
    for g, items in best.items():
        f.write(f"{g},#genre#\n")
        for item in items:
            f.write(item + "\n")
        f.write("\n")

print("✅ best_multicast.txt 已生成")
