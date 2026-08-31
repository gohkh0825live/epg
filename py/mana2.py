import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from xml.dom import minidom
import requests


def get_formatted_channel_id(ch_data):
    # 动态从 channelName 中提取纯英文字母和数字，拼接 .mana2
    # 例如: "TV1" -> "TV1.mana2" | "TV ALHIJRAH" -> "TVALHIJRAH.mana2" | "SUKAN+" -> "SUKAN.mana2"
    channel_name = ch_data.get("channelName", "")
    clean_name = re.sub(r"[^a-zA-Z0-9]", "", channel_name)

    if not clean_name:
        # 如果名称没有英文数字（例如纯中文或特殊字符），退回使用 slug/channelId
        clean_name = ch_data.get("slug") or ch_data.get("channelId") or "CHANNEL"

    return f"{clean_name}.mana2"


def parse_time(utc_str):
    cleaned_str = utc_str.rstrip("Z")
    if "." in cleaned_str:
        dt = datetime.strptime(cleaned_str, "%Y-%m-%dT%H:%M:%S.%f")
    else:
        dt = datetime.strptime(cleaned_str, "%Y-%m-%dT%H:%M:%S")

    myt_tz = timezone(timedelta(hours=8))
    dt_utc = dt.replace(tzinfo=timezone.utc)
    dt_local = dt_utc.astimezone(myt_tz)
    return dt_local.strftime("%Y%m%d%H%M%S +0800")


def json_to_xmltv(json_data):
    raw = json.loads(json_data) if isinstance(json_data, str) else json_data
    if not raw.get("success") or "data" not in raw:
        raise ValueError("Invalid JSON payload or status unsuccessful")

    tv = ET.Element(
        "tv",
        {
            "generator-info-name": "MYTV EPG Converter",
            "source-info-url": "https://co3y6iwoio.tenbytecdn.com",
        },
    )

    channels_data = raw["data"]

    # 1. 构建 <channel> 节点
    for ch in channels_data:
        formatted_id = get_formatted_channel_id(ch)
        channel_name = ch.get("channelName", "")
        logo_url = ch.get("channelLogo", "")

        channel_node = ET.SubElement(tv, "channel", {"id": formatted_id})
        display_name = ET.SubElement(channel_node, "display-name")
        display_name.text = channel_name

        if logo_url:
            ET.SubElement(channel_node, "icon", {"src": logo_url})

    # 2. 构建 <programme> 节点
    for ch in channels_data:
        formatted_id = get_formatted_channel_id(ch)
        programmes = ch.get("programmes", [])

        for prog in programmes:
            if prog.get("isGeneric"):
                continue

            start_time = parse_time(prog["startTime"])
            end_time = parse_time(prog["endTime"])

            prog_node = ET.SubElement(
                tv,
                "programme",
                {
                    "start": start_time,
                    "stop": end_time,
                    "channel": formatted_id,
                },
            )

            title = ET.SubElement(prog_node, "title", {"lang": "ms"})
            title.text = prog.get("title", "")

            desc_text = prog.get("description")
            if desc_text:
                desc = ET.SubElement(prog_node, "desc", {"lang": "ms"})
                desc.text = desc_text

            genre = prog.get("genre")
            if genre:
                category = ET.SubElement(prog_node, "category", {"lang": "en"})
                category.text = genre

    xml_str = ET.tostring(tv, encoding="utf-8")
    parsed_xml = minidom.parseString(xml_str)
    return parsed_xml.toprettyxml(indent="  ")


if __name__ == "__main__":
    myt_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = myt_now.strftime("%Y-%m-%d")

    API_URL = f"https://co3y6iwoio.tenbytecdn.com/api/v1/public/epg/guide?channelType=video&date={today_str}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.mana2.my/",
        "Origin": "https://www.mana2.my",
    }

    try:
        response = requests.get(API_URL, headers=headers, timeout=15)
        response.raise_for_status()

        xml_content = json_to_xmltv(response.text)

        with open("mana2.xml", "w", encoding="utf-8") as f:
            f.write(xml_content)

        print(f"[{today_str}] mana2.xml 已成功生成，所有 ID 均动态追加 .mana2！")

    except Exception as e:
        print(f"运行失败: {e}")
        exit(1)
