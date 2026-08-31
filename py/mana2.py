import json
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone, timedelta

def parse_time(utc_str):
    # 处理 ISO 时间字符串 (如 2026-09-02T16:00:00.000Z 或 2026-09-02T16:00:00Z)
    cleaned_str = utc_str.rstrip('Z')
    
    # 兼容带毫秒和不带毫秒的情况
    if '.' in cleaned_str:
        dt = datetime.strptime(cleaned_str, "%Y-%m-%dT%H:%M:%S.%f")
    else:
        dt = datetime.strptime(cleaned_str, "%Y-%m-%dT%H:%M:%S")

    # 转为 UTC+8 时区 (MYT/CST)
    myt_tz = timezone(timedelta(hours=8))
    dt_utc = dt.replace(tzinfo=timezone.utc)
    dt_local = dt_utc.astimezone(myt_tz)
    return dt_local.strftime("%Y%m%d%H%M%S +0800")

def json_to_xmltv(json_data):
    raw = json.loads(json_data) if isinstance(json_data, str) else json_data
    if not raw.get("success") or "data" not in raw:
        raise ValueError("Invalid JSON payload or status unsuccessful")

    tv = ET.Element('tv', {
        'generator-info-name': 'MYTV EPG Converter',
        'source-info-url': 'https://co3y6iwoio.tenbytecdn.com'
    })

    channels_data = raw["data"]

    # 1. 构建 <channel> 节点
    for ch in channels_data:
        channel_id = ch.get("slug") or ch.get("channelId")
        channel_name = ch.get("channelName", "")
        logo_url = ch.get("channelLogo", "")

        channel_node = ET.SubElement(tv, 'channel', {'id': str(channel_id)})
        display_name = ET.SubElement(channel_node, 'display-name')
        display_name.text = channel_name
        
        if logo_url:
            ET.SubElement(channel_node, 'icon', {'src': logo_url})

    # 2. 构建 <programme> 节点
    for ch in channels_data:
        channel_id = ch.get("slug") or ch.get("channelId")
        programmes = ch.get("programmes", [])

        for prog in programmes:
            # 忽略通用占位节目
            if prog.get("isGeneric"):
                continue

            start_time = parse_time(prog["startTime"])
            end_time = parse_time(prog["endTime"])

            prog_node = ET.SubElement(tv, 'programme', {
                'start': start_time,
                'stop': end_time,
                'channel': str(channel_id)
            })

            title = ET.SubElement(prog_node, 'title', {'lang': 'ms'})
            title.text = prog.get("title", "")

            desc_text = prog.get("description")
            if desc_text:
                desc = ET.SubElement(prog_node, 'desc', {'lang': 'ms'})
                desc.text = desc_text

            genre = prog.get("genre")
            if genre:
                category = ET.SubElement(prog_node, 'category', {'lang': 'en'})
                category.text = genre

    xml_str = ET.tostring(tv, encoding='utf-8')
    parsed_xml = minidom.parseString(xml_str)
    return parsed_xml.toprettyxml(indent="  ")

if __name__ == "__main__":
    # 获取马来西亚当前日期 (YYYY-MM-DD)
    myt_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = myt_now.strftime("%Y-%m-%d")

    # 接口地址与 Headers
    API_URL = f"https://co3y6iwoio.tenbytecdn.com/api/v1/public/epg/guide?channelType=video&date={today_str}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.mana2.my/",
        "Origin": "https://www.mana2.my"
    }

    try:
        response = requests.get(API_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        xml_content = json_to_xmltv(response.text)

        # 写入根目录下的 mana2.xml
        with open("mana2.xml", "w", encoding="utf-8") as f:
            f.write(xml_content)
            
        print(f"[{today_str}] mana2.xml 生成成功！")

    except Exception as e:
        print(f"运行失败: {e}")
        exit(1)
