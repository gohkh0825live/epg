import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone, timedelta

def json_to_xmltv(json_data):
    raw = json.loads(json_data)
    if not raw.get("success") or "data" not in raw:
        raise ValueError("Invalid JSON payload or status unsuccessful")

    tv = ET.Element('tv', {
        'generator-info-name': 'MYTV EPG Converter',
        'source-info-url': 'https://co3y6iwoio.tenbytecdn.com'
    })

    # 定义 UTC 和 MYT (UTC+8) 时区
    myt_tz = timezone(timedelta(hours=8))

    def parse_time(utc_str):
        # 解析 ISO 时间（假设带 'Z' 结尾）并转为 UTC+8
        dt = datetime.strptime(utc_str.rstrip('Z'), "%Y-%m-%dT%H:%M:%S.%f")
        dt_utc = dt.replace(tzinfo=timezone.utc)
        dt_local = dt_utc.astimezone(myt_tz)
        return dt_local.strftime("%Y%m%d%H%M%S +0800")

    channels_data = raw["data"]

    # 1. <channel> 节点
    for ch in channels_data:
        channel_id = ch.get("slug") or ch.get("channelId")
        channel_name = ch.get("channelName", "")
        logo_url = ch.get("channelLogo", "")

        channel_node = ET.SubElement(tv, 'channel', {'id': channel_id})
        display_name = ET.SubElement(channel_node, 'display-name')
        display_name.text = channel_name
        
        if logo_url:
            ET.SubElement(channel_node, 'icon', {'src': logo_url})

    # 2. <programme> 节点
    for ch in channels_data:
        channel_id = ch.get("slug") or ch.get("channelId")
        programmes = ch.get("programmes", [])

        for prog in programmes:
            if prog.get("isGeneric"):
                continue

            start_time = parse_time(prog["startTime"])
            end_time = parse_time(prog["endTime"])

            prog_node = ET.SubElement(tv, 'programme', {
                'start': start_time,
                'stop': end_time,
                'channel': channel_id
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
