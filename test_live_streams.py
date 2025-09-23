```python
#!/usr/bin/env python3
"""
直播源测速工具 - 专门测试央视和卫视频道
适用于 GitHub Actions 工作流
"""

import subprocess
import json
import requests
import time
import re
import os
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

class LiveStreamTester:
    def __init__(self, timeout=10, max_workers=5):
        self.timeout = timeout
        self.max_workers = max_workers
        self.results = []
        
        # 频道关键词过滤（央视和卫视）
        self.cctv_keywords = [
            'CCTV', '央视', '中央', 'cctv'
        ]
        self.ws_keywords = [
            '卫视', '卫视台', '电视台', 'TV'
        ]
        
        # 排除的关键词（非央视卫视）
        self.exclude_keywords = [
            '地方', '本地', '城市', '测试', '其他', '电影', '体育', '娱乐',
            '少儿', '动漫', '音乐', '教育', '纪实', '戏曲', '农业'
        ]

    def fetch_stream_list(self, url):
        """从URL获取直播源列表"""
        print(f"正在获取直播源列表: {url}")
        try:
            response = requests.get(url, timeout=15)
            response.encoding = 'utf-8'
            return response.text.splitlines()
        except Exception as e:
            print(f"获取直播源列表失败: {e}")
            return []

    def parse_stream_line(self, line):
        """解析单行直播源格式"""
        line = line.strip()
        if not line or line.startswith('#'):
            return None, None
            
        # 处理M3U格式: #EXTINF:-1,频道名称\nURL
        if line.startswith('#EXTINF'):
            return None, 'header'
        
        # 处理 txt 格式: 频道名称,URL
        if ',' in line:
            parts = line.split(',', 1)
            if len(parts) == 2:
                channel_name, url = parts
                return channel_name.strip(), url.strip()
        
        # 如果是纯URL，尝试从上一行获取频道名称
        if line.startswith('http'):
            return None, line
            
        return None, None

    def is_target_channel(self, channel_name):
        """判断是否为央视或卫视频道"""
        if not channel_name:
            return False
            
        channel_lower = channel_name.lower()
        
        # 检查排除关键词
        for keyword in self.exclude_keywords:
            if keyword in channel_lower:
                return False
        
        # 检查央视关键词
        for keyword in self.cctv_keywords:
            if keyword.lower() in channel_lower:
                return True
                
        # 检查卫视关键词
        for keyword in self.ws_keywords:
            if keyword.lower() in channel_lower:
                # 再次确认不是央视
                is_cctv = any(k.lower() in channel_lower for k in self.cctv_keywords)
                if not is_cctv:
                    return True
                    
        return False

    def test_single_stream(self, channel_name, stream_url):
        """测试单个直播源"""
        if not stream_url or not stream_url.startswith('http'):
            return None
            
        # 检查URL是否有效
        parsed_url = urlparse(stream_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return None
            
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams',
            '-rw_timeout', '5000000', '-probesize', '512',
            '-analyzeduration', '500000', '-timeout', '5000000',
            '-i', stream_url
        ]
        
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=self.timeout
            )
            response_time = round((time.time() - start_time) * 1000)
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    format_info = data.get('format', {})
                    streams = data.get('streams', [])
                    
                    # 获取流信息
                    video_stream = next((s for s in streams if s.get('codec_type') == 'video'), {})
                    audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), {})
                    
                    result_data = {
                        'channel': channel_name or '未知频道',
                        'url': stream_url,
                        'status': '有效',
                        'response_time_ms': response_time,
                        'duration': format_info.get('duration', 'N/A'),
                        'bit_rate': format_info.get('bit_rate', 'N/A'),
                        'video_codec': video_stream.get('codec_name', 'N/A'),
                        'video_resolution': f"{video_stream.get('width', 'N/A')}x{video_stream.get('height', 'N/A')}",
                        'audio_codec': audio_stream.get('codec_name', 'N/A')
                    }
                    print(f"✅ {channel_name or '未知频道'} - {response_time}ms")
                    return result_data
                    
                except json.JSONDecodeError:
                    pass
                    
            print(f"❌ {channel_name or '未知频道'} - 无效")
            return {
                'channel': channel_name or '未知频道',
                'url': stream_url,
                'status': '无效',
                'response_time_ms': response_time,
                'error': result.stderr
            }
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {channel_name or '未知频道'} - 超时")
            return {
                'channel': channel_name or '未知频道',
                'url': stream_url,
                'status': '超时',
                'response_time_ms': self.timeout * 1000
            }
        except Exception as e:
            print(f"❌ {channel_name or '未知频道'} - 错误: {e}")
            return {
                'channel': channel_name or '未知频道',
                'url': stream_url,
                'status': '错误',
                'response_time_ms': round((time.time() - start_time) * 1000),
                'error': str(e)
            }

    def process_stream_list(self, lines):
        """处理直播源列表"""
        print("开始解析直播源列表...")
        streams_to_test = []
        current_channel = None
        
        for i, line in enumerate(lines):
            channel_name, url = self.parse_stream_line(line)
            
            if channel_name and channel_name != 'header':
                current_channel = channel_name
            elif url and url != 'header':
                if current_channel and self.is_target_channel(current_channel):
                    streams_to_test.append((current_channel, url))
                current_channel = None
        
        print(f"找到 {len(streams_to_test)} 个央视/卫视频道待测试")
        return streams_to_test

    def run_test(self, source_url):
        """运行测试"""
        print("=== 直播源测速开始 ===")
        
        # 获取直播源列表
        lines = self.fetch_stream_list(source_url)
        if not lines:
            print("无法获取直播源列表")
            return False
            
        # 处理并过滤频道
        streams_to_test = self.process_stream_list(lines)
        if not streams_to_test:
            print("未找到符合条件的央视/卫视频道")
            return False
        
        # 并发测试
        print(f"开始并发测试（最大并发数: {self.max_workers}）...")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_stream = {
                executor.submit(self.test_single_stream, channel, url): (channel, url)
                for channel, url in streams_to_test
            }
            
            for future in as_completed(future_to_stream):
                result = future.result()
                if result:
                    self.results.append(result)
        
        return True

    def generate_output_files(self):
        """生成输出文件"""
        # 过滤有效源
        valid_streams = [r for r in self.results if r['status'] == '有效']
        valid_streams.sort(key=lambda x: x['response_time_ms'])
        
        print(f"\n=== 测试结果 ===")
        print(f"总测试数: {len(self.results)}")
        print(f"有效源: {len(valid_streams)}")
        print(f"有效率: {len(valid_streams)/len(self.results)*100:.1f}%")
        
        # 生成M3U文件
        m3u_content = "#EXTM3U\n"
        for stream in valid_streams:
            m3u_content += f"#EXTINF:-1,{stream['channel']}\n"
            m3u_content += f"{stream['url']}\n"
        
        # 生成TXT文件
        txt_content = ""
        for stream in valid_streams:
            txt_content += f"{stream['channel']},{stream['url']}\n"
        
        # 保存文件
        with open('valid_streams.m3u', 'w', encoding='utf-8') as f:
            f.write(m3u_content)
        
        with open('valid_streams.txt', 'w', encoding='utf-8') as f:
            f.write(txt_content)
        
        # 生成统计报告
        report = {
            'test_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_tested': len(self.results),
            'valid_count': len(valid_streams),
            'success_rate': round(len(valid_streams)/len(self.results)*100, 1),
            'results': self.results
        }
        
        with open('test_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n=== 输出文件 ===")
        print(f"📁 valid_streams.m3u - M3U格式有效源 ({len(valid_streams)}个)")
        print(f"📁 valid_streams.txt - TXT格式有效源")
        print(f"📁 test_report.json - 详细测试报告")
        
        # 显示前10个最快源
        if valid_streams:
            print(f"\n🚀 最快的前10个有效源:")
            for i, stream in enumerate(valid_streams[:10], 1):
                print(f"  {i:2d}. {stream['channel']:15} - {stream['response_time_ms']}ms")

def main():
    """主函数"""
    source_url = "https://ghfast.top/https://raw.githubusercontent.com/cnliux/cnliux.github.io/refs/heads/main/tv.txt"
    
    tester = LiveStreamTester(timeout=10, max_workers=8)
    
    if tester.run_test(source_url):
        tester.generate_output_files()
        print("\n🎉 测试完成！")
    else:
        print("\n❌ 测试失败！")
        exit(1)

if __name__ == "__main__":
    main()
```
