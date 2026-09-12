import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from xml.dom import minidom
import requests

# 静态 EPG 的基础 URL 结构
STATIC_EPG_BASE = "https://epg-exports-prod.s3.ap-southeast-1.amazonaws.com/epg-data/latest/"
IMG_BASE = "https://rtm-images.glueapi.io/fit-in/640x320/"


def get_formatted_channel_id(channel_name):
  """规范化频道 ID (去除特殊字符与后缀，追加 .rtmklik)"""
  clean_name = re.sub(
      r"\s*[\(\_]?HD[\)\_]?|\s*[\(\_]?SD[\)\_]?",
      "",
      channel_name,
      flags=re.IGNORECASE,
  )
  clean_id = re.sub(r"[^a-zA-Z0-9]", "", clean_name)
  return f"{clean_id or 'CHANNEL'}.rtmklik"


def parse_time(dt_str):
  """解析时间为标准 XMLTV 格式 (YYYYMMDDHHMMSS +0800)"""
  if not dt_str:
    return ""
  try:
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
  except ValueError:
    try:
      dt = datetime.fromisoformat(dt_str.rstrip("Z"))
    except Exception:
      return dt_str

  myt_tz = timezone(timedelta(hours=8))
  dt_local = dt.replace(tzinfo=myt_tz)
  return dt_local.strftime("%Y%m%d%H%M%S +0800")


def generate_weekly_xmltv(combined_schedules):
  """将 7 天的数据整合生成单份 XMLTV"""
  tv = ET.Element(
      "tv",
      {
          "generator-info-name": "RTMKlik Weekly EPG Converter",
          "source-info-url": "https://rtmklik.rtm.gov.my",
      },
  )

  channels_map = {}

  # 1. 提取全量频道并建立 <channel> 节点
  for item in combined_schedules:
    ch_info = item.get("channel", {})
    ch_name = (
        ch_info.get("title")
        if isinstance(ch_info, dict)
        else item.get("channelTitle")
    )

    if ch_name and ch_name not in channels_map:
      formatted_id = get_formatted_channel_id(ch_name)
      channels_map[ch_name] = formatted_id

      channel_node = ET.SubElement(tv, "channel", {"id": formatted_id})
      display_name = ET.SubElement(channel_node, "display-name")
      display_name.text = ch_name

  # 2. 生成所有 7 天的 <programme> 节点
  for item in combined_schedules:
    ch_info = item.get("channel", {})
    ch_name = (
        ch_info.get("title")
        if isinstance(ch_info, dict)
        else item.get("channelTitle")
    )

    if not ch_name or ch_name not in channels_map:
      continue

    formatted_id = channels_map[ch_name]
    start_raw = item.get("datetimeStart")
    end_raw = item.get("datetimeEnd")

    if not start_raw or not end_raw:
      continue

    prog_node = ET.SubElement(
        tv,
        "programme",
        {
            "start": parse_time(start_raw),
            "stop": parse_time(end_raw),
            "channel": formatted_id,
        },
    )

    prog_info = item.get("program", {})
    title_text = (
        prog_info.get("title")
        or item.get("title")
        or item.get("programTitle")
        or "Untitled"
    )
    desc_text = (
        prog_info.get("description")
        or item.get("description")
        or item.get("programDescription")
        or ""
    )
    photo_path = prog_info.get("photo") or item.get("photo")

    title = ET.SubElement(prog_node, "title", {"lang": "ms"})
    title.text = title_text

    if desc_text:
      desc = ET.SubElement(prog_node, "desc", {"lang": "ms"})
      desc.text = desc_text

    if photo_path:
      img_url = requests.compat.urljoin(IMG_BASE, photo_path)
      ET.SubElement(prog_node, "icon", {"src": img_url})

  xml_str = ET.tostring(tv, encoding="utf-8")
  parsed_xml = minidom.parseString(xml_str)
  return parsed_xml.toprettyxml(indent="  ")


if __name__ == "__main__":
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }

  url = f"{STATIC_EPG_BASE}epg_today.json"
  print(f"正在从 AWS S3 拉取 7 天全量 EPG 数据包: {url}")

  try:
    res = requests.get(url, headers=headers, timeout=25)
    res.raise_for_status()
    raw_json = res.json()

    # 提取 JSON 里的数据列表
    raw_data = raw_json.get("data", {})
    schedules = (
        raw_data.get("data", [])
        if isinstance(raw_data, dict)
        else raw_json.get("data", [])
    )

    if schedules:
      xml_content = generate_weekly_xmltv(schedules)
      with open("rtmklik.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)
      print(
          f"✅ 成功提取 {raw_json.get('dateStart')} 至"
          f" {raw_json.get('dateEnd')} 共 {len(schedules)} 条节目记录，已写入"
          " rtmklik.xml"
      )
    else:
      print("⚠️ 获取到的节目列表为空")

  except Exception as e:
    print(f"❌ 抓取或解析失败: {e}")
    exit(1)
