import json
import requests
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

# EPG 与 API 配置信息
CONFIG = {
    "DATA_URL": "https://epg-exports-prod.s3.ap-southeast-1.amazonaws.com/epg-data/latest/epg_today.json",
    "TIMEZONE": "+0800"  # 时区标识 (UTC+8)
}

def parse_iso_time(time_str):
    """解析 ISO 8601 时间字符串并转换为 XMLTV 格式 (YYYYMMDDhhmmss +0800)"""
    dt = datetime.fromisoformat(time_str)
    return dt.strftime("%Y%m%d%H%M%S") + f" {CONFIG['TIMEZONE']}"

def generate_epg():
    # 1. 获取 EPG JSON 数据
    print("Fetching EPG data...")
    response = requests.get(CONFIG["DATA_URL"])
    if response.status_code != 200:
        print(f"Failed to fetch data, status code: {response.status_code}")
        return
    
    epg_json = response.json()
    
    # 2. 创建 XMLTV 根节点
    tv_root = ET.Element("tv", {
        "generator-info-name": "RTM Klik EPG Generator",
        "source-info-url": epg_json.get("source", "")
    })
    
    channels_data = epg_json.get("data", {}).get("data", [])
    
    # 3. 处理频道与节目数据
    for channel_item in channels_data:
        channel_name = channel_item.get("channel")
        channel_id = str(channel_item.get("id"))
        
        # 添加 <channel> 节点
        channel_node = ET.SubElement(tv_root, "channel", id=channel_id)
        display_name = ET.SubElement(channel_node, "display-name", lang="ms")
        display_name.text = channel_name
        
        # 添加频道 Logo (如果有)
        channel_objs = channel_item.get("channelObj", [])
        if channel_objs:
            img_path = channel_objs[0].get("data", {}).get("images", {}).get("title", {}).get("path")
            if img_path:
                ET.SubElement(channel_node, "icon", src=f"https://rtm-images.glueapi.io/fit-in/640x320/{img_path}")

        # 处理频道的 EPG 节目单 <programme>
        schedule = channel_item.get("schedule", [])
        for prog in schedule:
            start_time = parse_iso_time(prog["dateTimeStart"])
            end_time = parse_iso_time(prog["dateTimeEnd"])
            
            prog_node = ET.SubElement(tv_root, "programme", {
                "start": start_time,
                "stop": end_time,
                "channel": channel_id
            })
            
            # 节目标题
            title = ET.SubElement(prog_node, "title", lang="ms")
            title.text = prog.get("scheduleProgramTitle") or prog.get("programTitle") or "No Title"
            
            # 节目简介
            desc_text = prog.get("scheduleProgramDescription") or prog.get("description")
            if desc_text:
                desc = ET.SubElement(prog_node, "desc", lang="ms")
                desc.text = desc_text
                
            # 集数 (如果有)
            ep_num = prog.get("scheduleEpisodeNumber") or prog.get("episodeNumber")
            if ep_num and ep_num > 0:
                episode = ET.SubElement(prog_node, "episode-num", system="onscreen")
                episode.text = f"EP {ep_num}"

    # 4. 格式化并保存 XML 文件
    xml_str = ET.tostring(tv_root, encoding="utf-8")
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml = parsed_xml.toprettyxml(indent="  ")
    
    output_filename = "rtmklik.xml"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(pretty_xml)
        
    print(f"EPG successfully generated and saved to '{output_filename}'.")

if __name__ == "__main__":
    generate_epg()
