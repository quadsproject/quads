#!/usr/bin/env python3
import asyncio
import calendar
import os
from datetime import datetime, timedelta

from quads.config import Config
from quads.tools.simple_table_generator import HostGenerate


async def main():
    generate = HostGenerate()
    months_out = 4
    now = datetime.now()
    dates = [now]

    for i in range(months_out):
        previous = dates[i]
        next_date = previous + timedelta(calendar.mdays[(previous.month % 12) + 1])
        dates.append(next_date)

    if not os.path.exists(Config["visual_web_dir"]):
        os.makedirs(Config["visual_web_dir"])

    for _date in dates:
        gen_time = "Allocation Map for %s-%.2d" % (_date.year, _date.month)
        content = await generate.generator(calendar.mdays[_date.month], _date.month, _date.year, gen_time)
        file_path = os.path.join(Config["visual_web_dir"], "%s-%.2d.html" % (_date.year, _date.month))
        with open(file_path, "wb+") as _file:
            _file.write(content.encode("utf-8"))
        os.chmod(file_path, 0o644)

    _current = os.path.join(Config["visual_web_dir"], "current.html")
    _next = os.path.join(Config["visual_web_dir"], "next.html")
    if os.path.lexists(_current):
        os.remove(_current)
    if os.path.lexists(_next):
        os.remove(_next)

    current_path = os.path.join(Config["visual_web_dir"], "%s-%.2d.html" % (dates[0].year, dates[0].month))
    os.symlink(current_path, _current)

    next_path = os.path.join(Config["visual_web_dir"], "%s-%.2d.html" % (dates[1].year, dates[1].month))
    os.symlink(next_path, _next)

    files = [html for html in os.listdir(Config["visual_web_dir"]) if ".html" in html]
    lines = []
    for file in files:
        if file != "current.html" and file != "next.html" and file != "index.html":
            line = "<a href=%s>%s</a>\n<br>\n" % (file, file.split(".")[0])
            lines.append(line)

    index_path = os.path.join(Config["visual_web_dir"], "index.html")
    with open(index_path, "w+") as index:
        print(f"File created on {index_path}")
        for line in lines:
            index.write(line)


if __name__ == "__main__":
    start_time = datetime.now()
    print(f"Start time: {start_time}")
    asyncio.run(main())
    print(f"End time: {datetime.now()}, Total time: {(datetime.now() - start_time).total_seconds()}s")
