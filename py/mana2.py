import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from xml.dom import minidom
import requests


def get_formatted_channel_id(ch_data):
    channel_name = ch_data.get("channelName", "").strip()

    # 清理常见干扰后缀（如 HD, SD 等）
    clean_name = re.sub(
        r"\s*[\(\_]?HD[\)\_]?|\s*[\(\_]?SD[\)\_]?",
        "",
        channel_name,
        flags=re.IGNORECASE,
    )

    # 去掉所有非英文字母和数字
    clean_id = re.sub(r"[^a-zA-Z0-9]", "", clean_name)

    if not clean_id:
        clean_id = (
            ch_data.get("slug") or ch_data.get("channelId") or "CHANNEL"
        )

    return f"{clean_id}.mana2"


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


def json_to_xmltv(combined_channels_data):
    tv = ET.Element(
        "tv",
        {
            "generator-info-name": "MYTV EPG Converter",
            "source-info-url": "https://co3y6iwoio.tenbytecdn.com",
        },
    )

    # 1. 构建 <channel> 节点
    for ch_id, ch in combined_channels_data.items():
        formatted_id = get_formatted_channel_id(ch)
        channel_name = ch.get("channelName", "")
        logo_url = ch.get("channelLogo", "")

        channel_node = ET.SubElement(tv, "channel", {"id": formatted_id})
        display_name = ET.SubElement(channel_node, "display-name")
        display_name.text = channel_name

        if logo_url:
            ET.SubElement(channel_node, "icon", {"src": logo_url})

    # 2. 构建 <programme> 节点
    for ch_id, ch in combined_channels_data.items():
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
    myt_tz = timezone(timedelta(hours=8))
    myt_now = datetime.now(myt_tz)

    # 计算今天与明天的日期字符串
    dates_to_fetch = [
        (myt_now).strftime("%Y-%m-%d"),
        (myt_now + timedelta(days=1)).strftime("%Y-%m-%d"),
    ]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.mana2.my/",
        "Origin": "https://www.mana2.my",
    }

    # 用于存放合并后的频道数据 { channel_id: channel_dict }
    combined_channels = {}

    for date_str in dates_to_fetch:
        API_URL = f"https://co3y6iwoio.tenbytecdn.com/api/v1/public/epg/guide?channelType=video&date={date_str}"
        print(f"正在抓取 [{date_str}] 的 EPG 数据...")

        try:
            response = requests.get(API_URL, headers=headers, timeout=15)
            response.raise_for_status()
            raw = response.json()

            if not raw.get("success") or "data" not in raw:
                continue

            for ch in raw["data"]:
                ch_key = ch.get("channelId") or ch.get("slug")
                if not ch_key:
                    continue

                if ch_key not in combined_channels:
                    # 如果未登记过该频道，存入基本属性及当前的节目
                    combined_channels[ch_key] = ch
                else:
                    # 如果已存在，合并 programmes 节目数据
                    existing_progs = combined_channels[ch_key].get(
                        "programmes", []
                    )
                    new_progs = ch.get("programmes", [])
                    combined_channels[ch_key]["programmes"] = (
                        existing_progs + new_progs
                    )

        except Exception as e:
            print(f"抓取 [{date_str}] 数据失败: {e}")

    # 生成 XMLTV 文本并写入文件
    if combined_channels:
        try:
            xml_content = json_to_xmltv(combined_channels)
            with open("mana2.xml", "w", encoding="utf-8") as f:
                f.write(xml_content)
            print(f"成功合并两天数据并写入 mana2.xml！")
        except Exception as e:
            print(f"生成 XML 失败: {e}")
            exit(1)
    else:
        print("未获取到任何 EPG 数据！")
        exit(1)
