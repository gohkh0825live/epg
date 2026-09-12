from datetime import datetime, timedelta, timezone
import json
import re
from xml.dom import minidom
import xml.etree.ElementTree as ET
import requests

# 配置文件中的基础参数
CONFIG = {
    "API_URL": "https://rtm.glueapi.io/v3/epg/channelSchedule",
    "API_URL_2": (
        "https://rtm-admin.glueapi.io/v3/epg/channelSchedule?sort=id&embed=program,channel&timezone=8&limit=0&ids={channel_id}&dateStart={date_start}&dateEnd={date_end}"
    ),
    "IMG_BASE": "https://rtm-images.glueapi.io/fit-in/640x320/",
    "EPG_CHANNEL_IDS": {
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
    },
}


def get_formatted_channel_id(channel_name):
  """规范化频道 ID，例如: BeritaRTM.rtmklik"""
  clean_name = re.sub(
      r"\s*[\(\_]?HD[\)\_]?|\s*[\(\_]?SD[\)\_]?",
      "",
      str(channel_name),
      flags=re.IGNORECASE,
  )
  clean_id = re.sub(r"[^a-zA-Z0-9]", "", clean_name)
  return f"{clean_id or 'CHANNEL'}.rtmklik"


def parse_time(dt_str):
  """转换为 XMLTV 时间格式: YYYYMMDDHHMMSS +0800"""
  if not dt_str:
    return ""
  dt_str = str(dt_str).strip()
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


def fetch_channel_list(headers):
  """获取全量频道映射表（配置映射 + API 全量获取）"""
  channels = dict(CONFIG["EPG_CHANNEL_IDS"])
  try:
    res = requests.get(CONFIG["API_URL"], headers=headers, timeout=15)
    if res.status_code == 200:
      raw = res.json()
      items = (
          raw.get("data", {}).get("data", [])
          if isinstance(raw.get("data"), dict)
          else raw.get("data", [])
      )
      for item in items:
        name = item.get("channel", "").strip()
        cid = item.get("id")
        if name and cid:
          channels[name] = cid
  except Exception as e:
    print(f"⚠️ API 频道列表获取失败，使用预设配置: {e}")
  return channels


def generate_xmltv():
  tv = ET.Element(
      "tv",
      {
          "generator-info-name": "RTMKlik XMLTV Converter",
          "source-info-url": "https://rtmklik.rtm.gov.my",
      },
  )

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      ),
      "Referer": "https://rtmklik.rtm.gov.my/",
  }

  myt_tz = timezone(timedelta(hours=8))
  now = datetime.now(myt_tz)
  date_start = now.strftime("%Y-%m-%d")
  date_end = (now + timedelta(days=1)).strftime("%Y-%m-%d")

  channels = fetch_channel_list(headers)
  print(f"📺 准备处理 {len(channels)} 个频道的 EPG...")

  # 1. 创建 <channel> 节点
  for name in channels.keys():
    formatted_id = get_formatted_channel_id(name)
    chan_node = ET.SubElement(tv, "channel", {"id": formatted_id})
    disp_node = ET.SubElement(chan_node, "display-name")
    disp_node.text = name

  # 2. 抓取具体节目数据并填充 <programme> 节点
  total_progs = 0
  for name, cid in channels.items():
    formatted_id = get_formatted_channel_id(name)
    api_url = CONFIG["API_URL_2"].format(
        channel_id=cid, date_start=date_start, date_end=date_end
    )

    try:
      res = requests.get(api_url, headers=headers, timeout=10)
      if res.status_code != 200:
        continue

      raw = res.json()
      schedules = raw.get("data", raw) if isinstance(raw, dict) else raw
      if isinstance(schedules, dict):
        schedules = schedules.get("data", [])

      for item in schedules:
        start_raw = item.get("datetimeStart") or item.get("dateStart")
        end_raw = item.get("datetimeEnd") or item.get("dateEnd")
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
        if not isinstance(prog_info, dict):
          prog_info = {}

        title_text = (
            prog_info.get("title") or item.get("title") or "Tanpa Tajuk"
        )
        desc_text = (
            prog_info.get("description") or item.get("description") or ""
        )
        photo_path = (
            prog_info.get("photo") or item.get("photo") or item.get("image")
        )

        title = ET.SubElement(prog_node, "title", {"lang": "ms"})
        title.text = str(title_text)

        if desc_text:
          desc = ET.SubElement(prog_node, "desc", {"lang": "ms"})
          desc.text = str(desc_text)

        if photo_path:
          img_url = requests.compat.urljoin(CONFIG["IMG_BASE"], str(photo_path))
          ET.SubElement(prog_node, "icon", {"src": img_url})

        total_progs += 1

      print(f"  └─ 频道 [{name}] 数据解析完成")
    except Exception as e:
      print(f"  ❌ 频道 [{name}] 抓取失败: {e}")

  print(f"\n📝 总共生成 {total_progs} 条节目节点")

  xml_str = ET.tostring(tv, encoding="utf-8")
  parsed_xml = minidom.parseString(xml_str)
  return parsed_xml.toprettyxml(indent="  ")


if __name__ == "__main__":
  xml_content = generate_xmltv()
  with open("rtmklik.xml", "w", encoding="utf-8") as f:
    f.write(xml_content)
  print("✅ 已成功重新生成完整的 rtmklik.xml！")
