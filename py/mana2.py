import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import pytz

def json_to_xmltv(json_data):
    # 解析 JSON 数据
    raw = json.loads(json_data)
    if not raw.get("success") or "data" not in raw:
        raise ValueError("Invalid JSON payload or status unsuccessful")

    # 创建 XMLTV 根节点
    tv = ET.Element('tv', {
        'generator-info-name': 'MYTV EPG Converter',
        'source-info-url': 'https://co3y6iwoio.tenbytecdn.com'
    })

    # 时区定义：UTC 与 目标时区 Asia/Kuala_Lumpur (+08:00)
    utc_tz = pytz.utc
    target_tz = pytz.timezone('Asia/Kuala_Lumpur')

    def parse_time(utc_str):
        # 转换 ISO 时间字符串为 XMLTV 时间格式 (YYYYMMDDhhmmss +0800)
        dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        dt_utc = utc_tz.localize(dt)
        dt_local = dt_utc.astimezone(target_tz)
        return dt_local.strftime("%Y%m%d%H%M%S %z")

    channels_data = raw["data"]

    # 1. 构建 <channel> 节点
    for ch in channels_data:
        channel_id = ch.get("slug") or ch.get("channelId")
        channel_name = ch.get("channelName", "")
        logo_url = ch.get("channelLogo", "")

        channel_node = ET.SubElement(tv, 'channel', {'id': channel_id})
        display_name = ET.SubElement(channel_node, 'display-name')
        display_name.text = channel_name
        
        if logo_url:
            ET.SubElement(channel_node, 'icon', {'src': logo_url})

    # 2. 构建 <programme> 节点
    for ch in channels_data:
        channel_id = ch.get("slug") or ch.get("channelId")
        programmes = ch.get("programmes", [])

        for prog in programmes:
            # 忽略通用占位节目 (isGeneric: true)
            if prog.get("isGeneric"):
                continue

            start_time = parse_time(prog["startTime"])
            end_time = parse_time(prog["endTime"])

            prog_node = ET.SubElement(tv, 'programme', {
                'start': start_time,
                'stop': end_time,
                'channel': channel_id
            })

            # 节目标题
            title = ET.SubElement(prog_node, 'title', {'lang': 'ms'})
            title.text = prog.get("title", "")

            # 节目简介
            desc_text = prog.get("description")
            if desc_text:
                desc = ET.SubElement(prog_node, 'desc', {'lang': 'ms'})
                desc.text = desc_text

            # 节目分类/类型
            genre = prog.get("genre")
            if genre:
                category = ET.SubElement(prog_node, 'category', {'lang': 'en'})
                category.text = genre

    # 美化 XML 输出结构
    xml_str = ET.tostring(tv, encoding='utf-8')
    parsed_xml = minidom.parseString(xml_str)
    return parsed_xml.toprettyxml(indent="  ")

# 使用示例
if __name__ == "__main__":
    # 读取输入的 JSON 文本
    with open("epg.json", "r", encoding="utf-8") as f:
        json_content = f.read()

    xmltv_output = json_to_xmltv(json_content)

    # 保存为 standard epg.xml 格式
    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(xmltv_output)
    print("EPG successfully converted to epg.xml")
