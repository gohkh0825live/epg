import os
import json
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

def fetch_and_convert_epg():
    # 获取 UTC+8 (Asia/Kuala_Lumpur) 的系统当前日期
    tz_plus_8 = ZoneInfo("Asia/Kuala_Lumpur")
    today_str = datetime.now(tz_plus_8).strftime("%Y-%m-%d")
    
    url = f"https://co3y6iwoio.tenbytecdn.com/api/v1/public/epg/guide?channelType=video&date={today_str}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.mana2.my",
        "Referer": "https://www.mana2.my/"
    }

    print(f"正在抓取 [UTC+8] 日期为 {today_str} 的 EPG 数据...")

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        json_data = response.json()

        # 构建 XMLTV 根节点
        tv = ET.Element('tv', generator_info_name='Auto-EPG-Converter')

        # 兼容处理 JSON 数据根节点
        channels_data = json_data
        if isinstance(json_data, dict):
            channels_data = json_data.get('data') or json_data.get('result') or json_data.get('channels') or []

        if not isinstance(channels_data, list):
            print("数据提取失败：无法读取到频道列表，请检查 API 返回格式")
            return

        # 遍历频道及节目表
        for item in channels_data:
            channel_id = str(item.get('channelId') or item.get('id') or item.get('code') or '')
            channel_name = str(item.get('channelName') or item.get('name') or channel_id)

            if not channel_id:
                continue

            # 创建 <channel> 节点
            ch_node = ET.SubElement(tv, 'channel', id=channel_id)
            display_node = ET.SubElement(ch_node, 'display-name')
            display_node.text = channel_name

            # 遍历该频道下的节目
            programs = item.get('programs') or item.get('epg') or item.get('list') or []
            for prog in programs:
                title = prog.get('title') or prog.get('name') or '未命名节目'
                
                # 时间提取与转换
                start_raw = prog.get('startTime') or prog.get('start')
                end_raw = prog.get('endTime') or prog.get('end')

                start_str, end_str = parse_epg_time(start_raw), parse_epg_time(end_raw)
                if not start_str or not end_str:
                    continue

                prog_node = ET.SubElement(tv, 'programme', start=start_str, stop=end_str, channel=channel_id)
                title_node = ET.SubElement(prog_node, 'title', lang='zh')
                title_node.text = title

                desc = prog.get('description') or prog.get('desc')
                if desc:
                    desc_node = ET.SubElement(prog_node, 'desc', lang='zh')
                    desc_node.text = str(desc)

        # 美化并输出 XML 文件
        raw_xml = ET.tostring(tv, encoding='utf-8')
        pretty_xml = minidom.parseString(raw_xml).toprettyxml(indent="  ")

        output_file = "mana2.xml"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(pretty_xml)

        print(f"转换成功！EPG 文件已更新保存至: {os.path.abspath(output_file)}")

    except Exception as e:
        print(f"处理失败，错误原因: {e}")

def parse_epg_time(time_val):
    """时间解析通用函数：转换各种格式时间为 XMLTV 标准格式 (YYYYMMDDhhmmss +0800)"""
    if not time_val:
        return None
    try:
        # 处理时间戳 (秒级 / 毫秒级)
        if isinstance(time_val, (int, float)) or (isinstance(time_val, str) and time_val.isdigit()):
            ts = int(time_val)
            if ts > 1e11:  # 毫秒级时间戳
                ts /= 1000
            # 明确按 UTC+8 解析 timestamp
            tz_plus_8 = timezone(timedelta(hours=8))
            dt = datetime.fromtimestamp(ts, tz=tz_plus_8)
            return dt.strftime('%Y%m%d%H%M%S +0800')
        
        # 处理字符串格式
        if isinstance(time_val, str):
            clean_val = time_val.replace('T', ' ').split('.')[0]
            dt = datetime.strptime(clean_val, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%Y%m%d%H%M%S +0800')
    except Exception:
        pass
    return None

if __name__ == "__main__":
    fetch_and_convert_epg()
