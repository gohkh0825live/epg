import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from xml.dom import minidom
import requests

# RTM 接口及配置参数
API_TEMPLATE = (
    "https://rtm-admin.glueapi.io/v3/epg/channelSchedule"
    "?sort=id&embed=program,channel&timezone=8&limit=0&ids={channel_id}&dateStart={date_str}&dateEnd={date_str}"
)
IMG_BASE = "https://rtm-images.glueapi.io/fit-in/640x320/"

CHANNEL_IDS = {
    "Berita RTM": 7,
    "RTM World": 61,
    "Dewan Rakyat": 9,
    "Dewan Negara": 10,
    "FIH 1": 94,
    "FIH 2": 95,
    "Roll": 70,
    "Lead": 81,
    "Jr.": 83,
    "Snap": 84,
    "Apetito": 85,
    "Aura": 88,
    "Fitrah": 89,
}


def get_formatted_channel_id(channel_name):
  """规范化频道 ID (格式如: BeritaRTM.rtmklik)"""
  clean_name = re.sub(
      r"\s*[\(\_]?HD[\)\_]?|\s*[\(\_]?SD[\)\_]?",
      "",
      channel_name,
      flags=re.IGNORECASE,
  )
  clean_id = re.sub(r"[^a-zA-Z0-9]", "", clean_name)
  return f"{clean_id or 'CHANNEL'}.rtmklik"


def parse_time(dt_str):
  """将时间解析为标准 XMLTV 格式 (YYYYMMDDHHMMSS +0800)"""
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


def json_to_xmltv(combined_channels_data):
  """构建 XMLTV 结构树"""
  tv = ET.Element(
      "tv",
      {
          "generator-info-name": "RTMKlik EPG Converter",
          "source-info-url": "https://rtmklik.rtm.gov.my",
      },
  )

  # 1. 构建 <channel> 节点
  for name in combined_channels_data.keys():
    formatted_id = get_formatted_channel_id(name)

    channel_node = ET.SubElement(tv, "channel", {"id": formatted_id})
    display_name = ET.SubElement(channel_node, "display-name")
    display_name.text = name

  # 2. 构建 <programme> 节点
  for name, programmes in combined_channels_data.items():
    formatted_id = get_formatted_channel_id(name)

    for prog in programmes:
      start_raw = prog.get("datetimeStart")
      end_raw = prog.get("datetimeEnd")

      if not start_raw or not end_raw:
        continue

      start_time = parse_time(start_raw)
      end_time = parse_time(end_raw)

      prog_node = ET.SubElement(
          tv,
          "programme",
          {
              "start": start_time,
              "stop": end_time,
              "channel": formatted_id,
          },
      )

      # 节目信息
      prog_info = prog.get("program", {})
      title_text = prog_info.get("title") or prog.get("title") or "Untitled"
      desc_text = prog_info.get("description") or prog.get("description") or ""
      photo_path = prog_info.get("photo") or prog.get("photo")

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
  myt_tz = timezone(timedelta(hours=8))
  myt_now = datetime.now(myt_tz)

  # 抓取两天（今天与明天）
  dates_to_fetch = [
      myt_now.strftime("%Y-%m-%d"),
      (myt_now + timedelta(days=1)).strftime("%Y-%m-%d"),
  ]

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      ),
      "Referer": "https://rtmklik.rtm.gov.my/",
      "Origin": "https://rtmklik.rtm.gov.my",
  }

  combined_channels = {name: [] for name in CHANNEL_IDS.keys()}

  for date_str in dates_to_fetch:
    print(f"正在抓取 [{date_str}] 的 RTMKlik EPG 数据...")

    for name, cid in CHANNEL_IDS.items():
      api_url = API_TEMPLATE.format(channel_id=cid, date_str=date_str)
      try:
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
        raw = response.json()

        progs = raw.get("data", raw) if isinstance(raw, dict) else raw
        if isinstance(progs, list):
          combined_channels[name].extend(progs)

      except Exception as e:
        print(f"  ❌ 抓取频道 [{name}] ({date_str}) 失败: {e}")

  # 导出为 rtmklik.xml
  if any(combined_channels.values()):
    try:
      xml_content = json_to_xmltv(combined_channels)
      with open("rtmklik.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)
      print("\n✅ 成功生成 XMLTV 文件: rtmklik.xml")
    except Exception as e:
      print(f"❌ 生成 XML 失败: {e}")
      exit(1)
  else:
    print("⚠️ 未获取到任何 EPG 数据！")
    exit(1)
