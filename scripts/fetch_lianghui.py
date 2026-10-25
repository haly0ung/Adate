#!/usr/bin/env python3
"""两会日期窗口抓取（只用 Python 标准库）。

运行窗口：每年 12 月 1 日至次年 3 月 4 日；窗口外直接退出，什么都不改。
抓取逻辑：取人大、政协、政府网首页，提取站内新闻链接并逐篇扫描，
只认正式决定措辞（“决定……于 3 月 X 日在北京召开”），“建议”召开的不算
（政协 12 月常有“建议”日期，正式决定可能压到会前几天才出）。
校验规则（有一条不满足就不写）：
  - 日期在 3 月 1–15 日之间；
  - 文中年份（若有）必须等于目标年份；无年份则按目标年份计；
  - 人大、政协各自独立写入，不要求两边同时抓到。
目标年份：12 月运行时为次年，1–3 月运行时为当年。
写出：只在抓到有效日期且与现存不同时，才更新 lianghui_actual.json；
抓不到、格式不对、源站不可达：一律不改文件，退出码 0（不让 Action 报错）。
"""

import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "lianghui_actual.json"

SOURCES = [
    "https://www.npc.gov.cn/",
    "https://www.cppcc.gov.cn/",
    "https://www.gov.cn/",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; calendar-lianghui-bot/1.0)"}
MAX_LINKS_PER_SOURCE = 40
TIMEOUT = 20

# 全国人大：十四届全国人大 X 次会议于（2027 年）3 月 X 日在北京召开
NPC_PATTERNS = [
    re.compile(r"全国人民代表大会.{0,40}?(?:将于|于)(?:(\d{4})年)?3月(\d{1,2})日"),
    re.compile(r"全国人大.{0,40}?(?:将于|于)(?:(\d{4})年)?3月(\d{1,2})日"),
]
# 全国政协：全国政协十四届 X 次会议于（2027 年）3 月 X 日在北京召开
CPPCC_PATTERNS = [
    re.compile(r"全国政协.{0,40}?(?:将于|于)(?:(\d{4})年)?3月(\d{1,2})日"),
    re.compile(r"政协全国委员会.{0,40}?(?:将于|于)(?:(\d{4})年)?3月(\d{1,2})日"),
]


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
    for enc in ("utf-8", "gbk", "gb2312"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def strip_tags(html):
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def extract_links(html, base):
    host = urlparse(base).netloc
    links, seen = [], set()
    for href in re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I):
        if href.startswith(("javascript:", "mailto:", "#")):
            continue
        url = urljoin(base, href)
        if urlparse(url).netloc != host:
            continue
        if re.search(r"\.(jpg|jpeg|png|gif|css|js|pdf|doc|zip)(\?|$)", url, re.I):
            continue
        if url not in seen:
            seen.add(url)
            links.append(url)
        if len(links) >= MAX_LINKS_PER_SOURCE:
            break
    return links


def find_date(text, patterns, target_year):
    """返回 (month, day) 或 None。含“建议”的匹配句视为建议而非决定，跳过。"""
    if "决定" not in text:
        return None
    for pat in patterns:
        for m in pat.finditer(text):
            ctx = text[max(0, m.start() - 30):m.end() + 10]
            if "建议" in ctx:
                continue
            year = int(m.group(1)) if m.group(1) else target_year
            day = int(m.group(2))
            if year == target_year and 1 <= day <= 15:
                return (3, day)
    return None


def main():
    today = date.today()
    if today.month == 12:
        target_year = today.year + 1
    elif today.month in (1, 2) or (today.month == 3 and today.day <= 4):
        target_year = today.year
    else:
        print("非窗口期（12 月 1 日–3 月 4 日外），不抓取。")
        return 0

    found = {}
    for src in SOURCES:
        try:
            home = fetch(src)
        except Exception as exc:  # noqa: BLE001 - 单源失败不影响其他源
            print(f"源站不可达，跳过：{src}（{exc}）")
            continue
        pages = [home]
        for link in extract_links(home, src):
            try:
                pages.append(fetch(link))
            except Exception:  # noqa: BLE001 - 单篇失败不影响其他篇
                continue
        for page in pages:
            text = strip_tags(page)
            if "npc" not in found:
                hit = find_date(text, NPC_PATTERNS, target_year)
                if hit:
                    found["npc"] = date(target_year, hit[0], hit[1]).isoformat()
            if "cppcc" not in found:
                hit = find_date(text, CPPCC_PATTERNS, target_year)
                if hit:
                    found["cppcc"] = date(target_year, hit[0], hit[1]).isoformat()
            if len(found) == 2:
                break
        if len(found) == 2:
            break

    if not found:
        print(f"未抓到 {target_year} 年两会正式决定日期，不改文件。")
        return 0

    try:
        current = json.loads(OUT.read_text(encoding="utf-8"))
        if not isinstance(current, dict):
            current = {}
    except (OSError, ValueError):
        current = {}
    entry = current.get(str(target_year), {})
    if not isinstance(entry, dict):
        entry = {}
    entry.update(found)
    if current.get(str(target_year)) == entry:
        print(f"{target_year} 年两会日期无变化：{entry}")
        return 0
    current[str(target_year)] = entry
    OUT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {target_year} 年两会日期：{entry}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
