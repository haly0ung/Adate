#!/usr/bin/env python3
"""生成 A 股高影响日历订阅 calendar.ics（GitHub Pages 订阅源）。

包含类别（按对 A 股影响大小）：
  1. 股指期货交割日：每月第三个星期五；交割日前 3 天每天 09:00 提醒一次，交割日当天 09:00 再提醒一次。
     同日亦为中金所股指期权（沪深300 IO、上证50 HO、中证1000 MO）到期日——中金所
     《股指期权合约交易细则》第 12 条：最后交易日为到期月份第三个星期五，遇假日顺延，
     到期日同最后交易日，现金交割；故不另设事件，在交割日事件中注明。
     注意：中金所没有中证 500 股指期权，IC 是中证 500 股指期货；IM 是中证 1000 股指期货，
     中证 1000 股指期权是 MO。
  2. 宏观数据：CPI/PPI、PMI、国民经济运行情况（GDP/工业/社零/固投）。
     2026 年为国家统计局官方发布日程表（初步日期，以统计局调整为准）；
     2027 年起官方日程未公布，按惯例推算并在标题标注（预估），公布后修正。
  3. 央行：LPR 每月 20 日报价、MLF 每月 25 日操作，遇周末顺延至下周一，遇节假日顺延（以央行公告为准）。
  4. 财报季：年报预告 1/31、年报+一季报 4/30、半年报预告 7/15、半年报 8/31、
     三季报预告 10/15、三季报 10/31，遇周末提前至前一个工作日（以交易所规定为准）。
  5. 指数调整：MSCI 季末最后一个交易日生效；富时罗素季月第三个周五后的周一生效（以指数公司公告为准）。
  6. 美联储议息：决议公布日（北京时间），即美国议息会议次日凌晨公布后的第一个 A 股交易日上午。
  7. 衍生品到期：ETF 期权每月第四个星期三；国债期货季月第二个星期五。
  8. 全国两会：2026 年政协 3 月 4 日、人大 3 月 5 日（实数）；2027 年起先按
     政协 3 月 4 日、人大 3 月 5 日标（预估），每年 12 月至次年 3 月 4 日的窗口期
     由 scripts/fetch_lianghui.py 抓取官方正式决定替换为实数（见 lianghui_actual.json）。
     注意人大和政协公布节奏不同：人大一般前一年 12 月底常委会决定（2026 年为
     2025 年 12 月 27 日，提前约 68 天）；政协可能压哨（2025 年为 3 月 1 日决定、
     3 月 4 日开幕，只提前 3 天），故窗口期后期需每天抓取。
  9. A 股休市：2026 年国务院放假安排对应的休市 block；2027 年放假安排公布后更新。
  10. 富时 A50 交割日：新交所富时中国 A50 指数期货，每月倒数第二个新加坡工作日
      （按周一至周五推算；若新交所月末遇新加坡假期则可能顺延一天，以新交所公告为准）。
      交割日前不设提前提醒，当天 09:00 事件即提醒。

不做进日历的（没有可提前排期的固定日期）：
  - 社融/金融数据：央行每月中旬公布，无固定日期。
  - 政治局会议、中央经济工作会议：无提前公布的固定日期，当天才知道。
  - 个股解禁、除权除息、打新：个股层面每天都有，不适合通用日历。

顺延与修正：法定假日导致的变动没有实时推送接口，统一用下面的数据表维护。
每年官方日程公布后，改这里的数据表并提交，Action 下次运行自动重新生成发布，
订阅端下次刷新即同步。

窗口：本月起往后 26 个月，GitHub Action 每周重新生成。
事件 UID 按类别+日期固定生成，重新生成不会导致订阅端出现重复事件。
只用标准库，Action 里不需要装任何依赖。
"""

import calendar as calmod
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

WINDOW_MONTHS = 26
OUT_FILE = Path(__file__).resolve().parent / "calendar.ics"

# ---------------- 股指期货交割日修正表 ----------------
# {"原定交割日": "实际交割日"}。2027 年中秋在 9 月 15 日（周三），若国务院把假期向后
# 桥接至 9 月 17 日，则 9 月 17 日（第三个周五）按中金所规则顺延至下一交易日 9 月 20 日（周一）；
# 若只放中秋当天，则 9 月 17 日正常交割。待官方节假日安排公布并确认后取消注释并改成实际日期。
# 同日亦为中金所股指期权（IO/HO/MO）到期日，顺延规则与期货相同。
FUTURES_OVERRIDES = {
    # "2027-09-17": "2027-09-20",
}

# ---------------- 国家统计局 2026 年官方发布日程表 ----------------
# 来源：国家统计局 Regular Press Release Calendar of NBS in 2026（2025-12-26 发布，初步日期）。
# CPI/PPI 均为 09:30；PMI 为当月数据（2 月 PMI 因春节顺延至 3 月 4 日）；
# 国民经济运行情况为 10:00，含 GDP（季度月份）及工业、社零、固投等月度数据，除 PMI 外均为上月/上季度数据。
NBS_2026_CPI = ["2026-01-09", "2026-02-11", "2026-03-09", "2026-04-10", "2026-05-11",
                "2026-06-10", "2026-07-09", "2026-08-09", "2026-09-09", "2026-10-14",
                "2026-11-09", "2026-12-09"]
NBS_2026_PMI = ["2026-01-31", "2026-03-04", "2026-03-31", "2026-04-30", "2026-05-31",
                "2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30", "2026-10-31",
                "2026-11-30", "2026-12-31"]
NBS_2026_ECON = ["2026-01-19", "2026-03-16", "2026-04-16", "2026-05-18", "2026-06-16",
                 "2026-07-15", "2026-08-17", "2026-09-15", "2026-10-19", "2026-11-16",
                 "2026-12-15"]

# ---------------- 美联储议息决议公布日（北京时间日期） ----------------
# 美国议息会议次日凌晨（美东 14:00）公布，日期为公布后的第一个 A 股交易日上午提醒。
# 2026/2027 会议日程来自美联储官方 FOMC 日历；2028 年目前只公布了 1 月会议。
FOMC = ["2026-01-29", "2026-03-19", "2026-04-30", "2026-06-18", "2026-07-30",
        "2026-09-17", "2026-10-29", "2026-12-10",
        "2027-01-28", "2027-03-18", "2027-04-29", "2027-06-10", "2027-07-29",
        "2027-09-16", "2027-10-28", "2027-12-09",
        "2028-01-27"]

# ---------------- MSCI 指数季度调整生效日 ----------------
# 2026 年 2/5/8 月为 MSCI 官方公告的收盘生效日；11 月及以后按惯例（季末最后一个交易日），以 MSCI 公告为准。
MSCI = ["2026-02-27", "2026-05-29", "2026-08-31", "2026-11-30"]

# ---------------- 全国两会 ----------------
# 2026 年：政协十四届四次会议 3 月 4 日开幕，人大十四届四次会议 3 月 5 日开幕（政府工作报告）。
LIANGHUI = [("2026-03-04", "全国政协十四届四次会议开幕"),
            ("2026-03-05", "全国人大十四届四次会议开幕（政府工作报告）")]
# 2027 年起的实数由窗口抓取脚本写入 lianghui_actual.json，格式：
# {"2027": {"cppcc": "2027-03-04", "npc": "2027-03-05"}}；没有实数的年份用 3 月 4/5 日预估。
LIANGHUI_ACTUAL_PATH = Path(__file__).resolve().parent / "lianghui_actual.json"


def load_lianghui_actual():
    try:
        data = json.loads(LIANGHUI_ACTUAL_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

# ---------------- A 股休市 block（2026 年国务院放假安排） ----------------
# (开始, 结束次日, 名称)。市场周六周日恒休市，这里列的是法定假期 block。
HOLIDAYS_2026 = [("2026-01-01", "2026-01-04", "元旦"),
                 ("2026-02-15", "2026-02-24", "春节"),
                 ("2026-04-04", "2026-04-07", "清明"),
                 ("2026-05-01", "2026-05-06", "劳动节"),
                 ("2026-06-19", "2026-06-22", "端午"),
                 ("2026-09-25", "2026-09-28", "中秋"),
                 ("2026-10-01", "2026-10-08", "国庆")]


def d(s):
    return date.fromisoformat(s)


def fold(line):
    """按 ICS 规范把超长行折成每行不超过 75 字节（不拆 UTF-8 字符）。"""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not parts else 74
        if len(cur) + len(b) > limit:
            parts.append(cur)
            cur = b
        else:
            cur += b
    parts.append(cur)
    out = [parts[0].decode("utf-8")]
    for p in parts[1:]:
        out.append(" " + p.decode("utf-8"))
    return "\r\n".join(out)


def timed_event(lines, uid, summary, desc, day):
    lines.append("BEGIN:VEVENT")
    lines.append(f"UID:{uid}@ashare-calendar")
    lines.append(f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    lines.append(f"DTSTART;TZID=Asia/Shanghai:{day.strftime('%Y%m%dT090000')}")
    lines.append(f"DTEND;TZID=Asia/Shanghai:{day.strftime('%Y%m%dT093000')}")
    lines.append(f"SUMMARY:{summary}")
    lines.append(f"DESCRIPTION:{desc}")
    lines.append("BEGIN:VALARM")
    lines.append("TRIGGER:-PT0M")
    lines.append("ACTION:DISPLAY")
    lines.append(f"DESCRIPTION:{summary}")
    lines.append("END:VALARM")
    lines.append("END:VEVENT")


def allday_event(lines, uid, summary, desc, start, end_exclusive):
    lines.append("BEGIN:VEVENT")
    lines.append(f"UID:{uid}@ashare-calendar")
    lines.append(f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    lines.append(f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}")
    lines.append(f"DTEND;VALUE=DATE:{end_exclusive.strftime('%Y%m%d')}")
    lines.append(f"SUMMARY:{summary}")
    lines.append(f"DESCRIPTION:{desc}")
    lines.append("END:VEVENT")


def nth_weekday(year, month, weekday, n):
    """第 n 个星期几（weekday: 0=周一..6=周日）。"""
    weeks = calmod.monthcalendar(year, month)
    days = [w[weekday] for w in weeks if w[weekday] != 0]
    return date(year, month, days[n - 1])


def last_day(year, month):
    return date(year, month, calmod.monthrange(year, month)[1])


def next_monday_if_weekend(day):
    if day.weekday() == 5:
        return day + timedelta(days=2)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def last_weekday_on_or_before(day):
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def second_last_business_day(year, month):
    """每月倒数第二个工作日（周一至周五，不含新加坡假期；月末遇新加坡假期时
    实际日期可能提前一天，以新交所公告为准）。"""
    days = [date(year, month, d) for d in range(1, calmod.monthrange(year, month)[1] + 1)
            if date(year, month, d).weekday() < 5]
    return days[-2]


def months_window(n):
    today = date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def in_window(day, start, end):
    return start <= day < end


def main():
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//A股高影响日历订阅//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Shanghai",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0800",
        "TZOFFSETTO:+0800",
        "TZNAME:CST",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]
    months = months_window(WINDOW_MONTHS)
    win_start = date(months[0][0], months[0][1], 1)
    win_end = date(months[-1][0], months[-1][1], 1) + timedelta(days=32)
    win_end = date(win_end.year, win_end.month, 1)
    count = 0

    def add(uid, summary, desc, day):
        nonlocal count
        if in_window(day, win_start, win_end):
            timed_event(lines, uid, summary, desc, day)
            count += 1

    # ---- 1. 股指期货交割日 ----
    for y, m in months:
        planned = nth_weekday(y, m, 4, 3)  # 第三个星期五
        actual = d(FUTURES_OVERRIDES.get(planned.isoformat(), planned.isoformat()))
        for delta, label, left in ((3, "3天后交割", "还有3天"), (2, "2天后交割", "还有2天"), (1, "明天交割", "明天就是交割日")):
            dd = actual - timedelta(days=delta)
            add(f"futures-remind-{dd.isoformat().replace('-', '')}",
                f"股指期货交割提醒（{label}）",
                f"股指期货交割日为{actual.isoformat()}，{left}，记得提前移仓/平仓。", dd)
        note = "" if actual == planned else f"（原定{planned.isoformat()}，遇法定假日顺延）"
        add(f"futures-delivery-{actual.isoformat().replace('-', '')}",
            "股指期货交割日",
            f"股指期货（IF/IC/IM/IH）交割日{note}；同日亦为中金所股指期权（沪深300 IO、上证50 HO、中证1000 MO）到期日；遇法定假日顺延，以交易所公告为准。", actual)

    # ---- 2. 宏观数据（2026 官方表 + 2027 起预估） ----
    for s in NBS_2026_CPI:
        add(f"macro-cpi-{s.replace('-', '')}", "CPI、PPI公布",
            "国家统计局公布上月 CPI、PPI（09:30）。", d(s))
    for s in NBS_2026_PMI:
        label = "2月" if s == "2026-03-04" else f"{int(s[5:7])}月"
        note = "（春节顺延至3月4日）" if s == "2026-03-04" else ""
        add(f"macro-pmi-{s.replace('-', '')}", f"PMI公布（{label}）",
            f"国家统计局公布{label}制造业 PMI（09:30）{note}。", d(s))
    for s in NBS_2026_ECON:
        add(f"macro-econ-{s.replace('-', '')}", "国民经济运行情况公布（GDP/工业/社零/固投）",
            "国家统计局公布国民经济运行情况（10:00），包括 GDP（季度月份）及工业生产、社零、固投等月度数据；除 PMI 外均为上月/上季度数据。", d(s))
    # 2027 年起：官方日程未公布，按惯例推算并标注（预估）
    for y, m in months:
        if (y, m) <= (2026, 12):
            continue
        cpi = next_monday_if_weekend(date(y, m, 10))
        add(f"macro-cpi-est-{cpi.isoformat().replace('-', '')}", "CPI、PPI公布（预估）",
            "2027 年起统计局日程未公布，按惯例（每月 10 日前后）推算，以统计局公告为准。", cpi)
        if m == 2:
            pmi = date(y, 3, 1)  # 2 月 PMI 受春节影响，顺延至 3 月初（预估）
        else:
            pmi = last_day(y, m)
        add(f"macro-pmi-est-{pmi.isoformat().replace('-', '')}", "PMI公布（预估）",
            "2027 年起统计局日程未公布，按惯例（月末）推算，以统计局公告为准。", pmi)
        if m != 2:
            gdp = next_monday_if_weekend(date(y, m, 16))
            add(f"macro-econ-est-{gdp.isoformat().replace('-', '')}",
                "国民经济运行情况公布（预估）",
                "2027 年起统计局日程未公布，按惯例（月中）推算，以统计局公告为准。", gdp)

    # ---- 3. 央行：LPR、MLF ----
    for y, m in months:
        lpr = next_monday_if_weekend(date(y, m, 20))
        est = ""
        if (y, m) == (2026, 2):
            lpr, est = date(2026, 2, 24), "（预估）"  # 2 月 20 日适逢春节假期，顺延至节后首个工作日
        add(f"pboc-lpr-{lpr.isoformat().replace('-', '')}", f"LPR报价{est}",
            "央行公布贷款市场报价利率（LPR），每月 20 日报价，遇节假日顺延，以央行公告为准。", lpr)
        mlf = next_monday_if_weekend(date(y, m, 25))
        if (y, m) == (2026, 9):
            mlf, est = date(2026, 9, 28), "（预估）"  # 9 月 25 日为中秋假期，顺延至节后首个工作日
        else:
            est = ""
        add(f"pboc-mlf-{mlf.isoformat().replace('-', '')}", f"MLF操作{est}",
            "央行开展中期借贷便利（MLF）操作，每月 25 日前后，遇节假日顺延，以央行公告为准。", mlf)

    # ---- 4. 财报季 ----
    for y, m in months:
        if m == 1:
            dd = last_weekday_on_or_before(date(y, 1, 31))
            add(f"report-{y}-annual-forecast", "年报业绩预告披露截止日",
                "上市公司年报业绩预告披露截止日（遇周末提前至前一个工作日，以交易所规定为准）。", dd)
        if m == 4:
            dd = last_weekday_on_or_before(date(y, 4, 30))
            add(f"report-{y}-annual", "年报+一季报披露截止日",
                "上市公司年报、一季报披露截止日（遇周末提前至前一个工作日，以交易所规定为准）。", dd)
        if m == 7:
            dd = last_weekday_on_or_before(date(y, 7, 15))
            add(f"report-{y}-interim-forecast", "半年报业绩预告披露截止日",
                "上市公司半年报业绩预告披露截止日（遇周末提前至前一个工作日，以交易所规定为准）。", dd)
        if m == 8:
            dd = last_weekday_on_or_before(date(y, 8, 31))
            add(f"report-{y}-interim", "半年报披露截止日",
                "上市公司半年报披露截止日（遇周末提前至前一个工作日，以交易所规定为准）。", dd)
        if m == 10:
            dd = last_weekday_on_or_before(date(y, 10, 15))
            add(f"report-{y}-q3-forecast", "三季报业绩预告披露截止日",
                "上市公司三季报业绩预告披露截止日（遇周末提前至前一个工作日，以交易所规定为准）。", dd)
            dd = last_weekday_on_or_before(date(y, 10, 31))
            add(f"report-{y}-q3", "三季报披露截止日",
                "上市公司三季报披露截止日（遇周末提前至前一个工作日，以交易所规定为准）。", dd)

    # ---- 5. 指数调整 ----
    for s in MSCI:
        add(f"msci-{s.replace('-', '')}", "MSCI指数季度调整生效",
            "MSCI 指数季度调整收盘后生效，被动资金进出集中在尾盘，以 MSCI 公告为准。", d(s))
    for y, m in months:
        if (y, m) <= (2026, 11):
            continue
        if m in (2, 5, 8, 11):
            dd = last_weekday_on_or_before(last_day(y, m))
            add(f"msci-{dd.isoformat().replace('-', '')}", "MSCI指数季度调整生效",
                "按 MSCI 惯例（季末最后一个交易日）推算，以 MSCI 公告为准。", dd)
        if m in (3, 6, 9, 12):
            dd = nth_weekday(y, m, 4, 3) + timedelta(days=3)  # 第三个周五后的周一
            add(f"ftse-{dd.isoformat().replace('-', '')}", "富时罗素指数季度调整生效",
                "富时罗素中国指数系列季度调整开盘前生效，以富时罗素公告为准。", dd)

    # ---- 6. 美联储议息 ----
    for s in FOMC:
        add(f"fomc-{s.replace('-', '')}", "美联储议息决议公布",
            "美联储议息会议决议已于今日凌晨（北京时间）公布，关注对今日 A 股开盘的影响。", d(s))

    # ---- 7. 衍生品到期 ----
    for y, m in months:
        dd = nth_weekday(y, m, 2, 4)  # 每月第四个星期三
        add(f"etf-opt-{dd.isoformat().replace('-', '')}", "ETF期权到期日",
            "上证 50ETF 期权、沪深 300ETF 期权到期日（每月第四个星期三），到期日效应留意尾盘波动。", dd)
        if m in (3, 6, 9, 12):
            dd = nth_weekday(y, m, 4, 2)  # 季月第二个星期五
            add(f"treasury-{dd.isoformat().replace('-', '')}", "国债期货交割日",
                "国债期货（季月合约）交割日，关注债市与资金面联动。", dd)

    # ---- 8. 全国两会 ----
    for s, title in LIANGHUI:
        add(f"lianghui-{s.replace('-', '')}", title,
            "全国两会期间关注政府工作报告及政策信号对市场的影响。", d(s))
    actual = load_lianghui_actual()
    years_real = {int(s[:4]) for s, _ in LIANGHUI} | {int(y) for y in actual}
    for y in sorted({yy for yy, _ in months}):
        if y in years_real:
            for key, title in (("cppcc", "全国政协会议开幕"), ("npc", "全国人大会议开幕（政府工作报告）")):
                s = actual.get(str(y), {}).get(key)
                if s:
                    add(f"lianghui-{s.replace('-', '')}", title,
                        "全国两会期间关注政府工作报告及政策信号对市场的影响（官方正式决定日期）。", d(s))
            continue
        if y < 2027:
            continue
        # 没有实数的年份：按近年惯例（政协 3 月 4 日、人大 3 月 5 日）标预估占位，
        # 窗口抓取到官方正式决定后由 lianghui_actual.json 替换。
        add(f"lianghui-est-{y}-cppcc", "全国政协会议开幕（预估）",
            "按近年惯例（政协 3 月 4 日）推算，官方正式决定公布后以抓取结果为准。", date(y, 3, 4))
        add(f"lianghui-est-{y}-npc", "全国人大会议开幕（预估）",
            "按近年惯例（人大 3 月 5 日）推算，官方正式决定公布后以抓取结果为准。", date(y, 3, 5))

    # ---- 10. 富时 A50 交割日（新交所） ----
    for y, m in months:
        dd = second_last_business_day(y, m)
        add(f"a50-{dd.isoformat().replace('-', '')}", "富时A50交割日",
            "新交所富时中国 A50 指数期货交割日（每月倒数第二个新加坡工作日）；"
            "交割前后留意夜盘对次日 A 股开盘情绪的影响，以新交所公告为准。", dd)

    # ---- 9. A 股休市 ----
    for s, e, name in HOLIDAYS_2026:
        start, end = d(s), d(e)
        if in_window(start, win_start, win_end):
            allday_event(lines, f"holiday-{s.replace('-', '')}", f"A股休市（{name}）",
                         f"A股休市（{name}假期），休市期间留意港股、美股及假期消息面对节后开盘的影响。",
                         start, end)
            count += 1

    lines.append("END:VCALENDAR")
    text = "\r\n".join(fold(l) for l in lines) + "\r\n"
    OUT_FILE.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_FILE} with {count} events")


if __name__ == "__main__":
    main()
