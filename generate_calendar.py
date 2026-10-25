#!/usr/bin/env python3
"""生成股指期货交割日订阅日历 calendar.ics。

规则：
- 每月第三个星期五为交割日（IF/IC/IM/IH）。
- 交割日前 3 天每天 09:00 提醒一次（前 3 天、前 2 天、前 1 天），交割日当天 09:00 再提醒一次。
- 窗口：本月起往后 26 个月，GitHub Action 每周重新生成，订阅端自动同步。

顺延：
- 法定假日导致的交割日变动没有公开实时接口，无法全自动感知。
  每年节假日安排公布后，把受影响的月份写进下面的 OVERRIDES，
  下次 Action 运行就会自动重新生成并发布，订阅端下次刷新即同步。
- 2027 年的节假日安排尚未公布，当前 2027 年的日期全部按第三个周五排，
  安排公布后再补 OVERRIDES。

UID 是按日期固定生成的，重新生成不会导致订阅端出现重复事件。
只用标准库，Action 里不需要装任何依赖。
"""

import calendar as calmod
from datetime import date, datetime, timezone
from pathlib import Path

# 交割日修正表：{"原定交割日": "实际交割日"}。
# 例：2027 年中秋在 9 月 15 日（周三），9 月 17 日（第三个周五）很可能撞上中秋假期需顺延，
# 待官方节假日安排公布并确认实际日期后，取消下面这行的注释并改成实际日期。
OVERRIDES = {
    # "2027-09-17": "2027-09-20",
}

WINDOW_MONTHS = 26
OUT_FILE = Path(__file__).resolve().parent / "calendar.ics"


def third_friday(year, month):
    weeks = calmod.monthcalendar(year, month)
    fridays = [w[calmod.FRIDAY] for w in weeks if w[calmod.FRIDAY] != 0]
    return date(year, month, fridays[2])


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


def event(lines, uid, summary, desc, day):
    ds = day.strftime("%Y%m%dT090000")
    de = day.strftime("%Y%m%dT093000")
    lines.append("BEGIN:VEVENT")
    lines.append(f"UID:{uid}@futures-calendar")
    lines.append(f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    lines.append(f"DTSTART;TZID=Asia/Shanghai:{ds}")
    lines.append(f"DTEND;TZID=Asia/Shanghai:{de}")
    lines.append(f"SUMMARY:{summary}")
    lines.append(f"DESCRIPTION:{desc}")
    lines.append("BEGIN:VALARM")
    lines.append("TRIGGER:-PT0M")
    lines.append("ACTION:DISPLAY")
    lines.append(f"DESCRIPTION:{summary}")
    lines.append("END:VALARM")
    lines.append("END:VEVENT")


def main():
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//股指期货交割日订阅//CN",
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
    count = 0
    for y, m in months_window(WINDOW_MONTHS):
        planned = third_friday(y, m)
        actual = date.fromisoformat(OVERRIDES.get(planned.isoformat(), planned.isoformat()))
        for delta, label, left in ((3, "3天后交割", "还有3天"), (2, "2天后交割", "还有2天"), (1, "明天交割", "明天就是交割日")):
            d = date.fromordinal(actual.toordinal() - delta)
            event(lines, f"futures-remind-{d.isoformat().replace('-', '')}",
                  f"股指期货交割提醒（{label}）",
                  f"股指期货交割日为{actual.isoformat()}，{left}，记得提前移仓/平仓。",
                  d)
            count += 1
        note = "" if actual == planned else f"（原定{planned.isoformat()}，遇法定假日顺延）"
        event(lines, f"futures-delivery-{actual.isoformat().replace('-', '')}",
              "股指期货交割日",
              f"股指期货（IF/IC/IM/IH）交割日{note}；遇法定假日顺延，以交易所公告为准。",
              actual)
        count += 1
    lines.append("END:VCALENDAR")
    text = "\r\n".join(fold(l) for l in lines) + "\r\n"
    OUT_FILE.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_FILE} with {count} events")


if __name__ == "__main__":
    main()
