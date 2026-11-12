import dayjs from "dayjs";
import utc from "dayjs/plugin/utc.js";
import duration from "dayjs/plugin/duration.js";
import relativeTime from "dayjs/plugin/relativeTime.js";
dayjs.extend(utc); dayjs.extend(duration); dayjs.extend(relativeTime);
const d = dayjs.utc("2024-02-28T10:20:30Z");
console.log(d.add(1, "day").format("YYYY-MM-DD dddd"), d.startOf("month").toISOString(), d.diff(dayjs.utc("2020-01-01"), "day"),
  dayjs.duration(90061, "seconds").format("D[d] HH:mm:ss"), d.from(d.add(3, "hour")), d.isLeapYear?.() ?? "noleap", d.daysInMonth());
