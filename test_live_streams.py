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
                        'video_codec': video
