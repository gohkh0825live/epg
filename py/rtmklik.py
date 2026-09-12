import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from xml.dom import minidom
import requests

STATIC_EPG_URL = "https://epg-exports-prod.s3.ap-southeast-1.amazonaws.com/epg-data/latest/epg_today.json"
IMG_BASE = "https://rtm-images.glueapi.io/fit-in/640x320/"


def get_formatted_channel_id(channel_name):
  """规范化频道 ID (去除特殊字符，追加 .rtmklik)"""
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
      dt = datetime.fromisoformat(str(dt_str).rstrip("Z"))
    except Exception:
      return str(dt_str)

  myt_tz = timezone(timedelta(hours=8))
  dt_local = dt.replace(tzinfo=myt_tz)
  return dt_local.strftime("%Y%m%d%H%M%S +0800")


def extract_schedules_list(raw_json):
  """递归解包数据，确保准确获取节目数组"""
  if isinstance(raw_json, list):
    return raw_json
  if isinstance(raw_json, dict):
    data_node = raw_json.get("data")
    if isinstance(data_node, list):
      return data_node
    elif isinstance(data_node, dict):
      return data_node.get("data", [])
  return []


def generate_xmltv(raw_json):
  """构建 XMLTV 结构树"""
  tv = ET.Element(
      "tv",
      {
          "generator-info-name": "RTMKlik EPG Converter",
          "source-info-url": "https://rtmklik.rtm.gov.my",
      },
  )

  schedules = extract_schedules_list(raw_json)
  print(f"解析到节目记录总条数: {len(schedules)}")

  if not schedules:
    return ET.tostring(tv, encoding="utf-8")

  channels_map = {}

  # 1. 提取所有频道并创建 <channel> 节点
  for item in schedules:
    ch_info = item.get("channel", {})
    if isinstance(ch_info, dict):
      ch_name = (
          ch_info.get("title") or ch_info.get("name") or ch_info.get("channel")
      )
    else:
      ch_name = (
          item.get("channelTitle") or item.get("channelName") or str(ch_info)
      )

    if ch_name and ch_name not in channels_map:
      formatted_id = get_formatted_channel_id(ch_name)
      channels_map[ch_name] = formatted_id

      channel_node = ET.SubElement(tv, "channel", {"id": formatted_id})
      display_name = ET.SubElement(channel_node, "display-name")
      display_name.text = ch_name

  print(f"成功识别频道数量: {len(channels_map)}")

  # 2. 生成所有 <programme> 节点
  for item in schedules:
    ch_info = item.get("channel", {})
    if isinstance(ch_info, dict):
      ch_name = (
          ch_info.get("title") or ch_info.get("name") or ch_info.get("channel")
      )
    else:
      ch_name = (
          item.get("channelTitle") or item.get("channelName") or str(ch_info)
      )

    if not ch_name or ch_name not in channels_map:
      continue

    formatted_id = channels_map[ch_name]
    start_raw = (
        item.get("datetimeStart")
        or item.get("dateStart")
        or item.get("startTime")
    )
    end_raw = (
        item.get("datetimeEnd") or item.get("dateEnd") or item.get("endTime")
    )

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

    # 兼容多种数据层级的字段读取
    prog_info = item.get("program", {})
    if not isinstance(prog_info, dict):
      prog_info = {}

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
    photo_path = (
        prog_info.get("photo") or item.get("photo") or item.get("image")
    )

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

  print(f"正在读取全量 EPG JSON: {STATIC_EPG_URL}")
  try:
    res = requests.get(STATIC_EPG_URL, headers=headers, timeout=25)
    res.raise_for_status()
    raw_json = res.json()

    xml_content = generate_xmltv(raw_json)

    with open("rtmklik.xml", "w", encoding="utf-8") as f:
      f.write(xml_content)

    print("✅ 成功重新写入 rtmklik.xml")

  except Exception as e:
    print(f"❌ 执行发生错误: {e}")
    exit(1)
