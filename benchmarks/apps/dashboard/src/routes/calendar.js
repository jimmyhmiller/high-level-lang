import { startOfMonth, endOfMonth, startOfWeek, endOfWeek, eachDayOfInterval, format, isWeekend, isSameMonth, addMonths, parseISO, differenceInCalendarDays, isBefore } from "date-fns";
import { groupBy } from "lodash-es";
import { h, rendered } from "../h.js";
import { Page } from "../layout.js";
import { projects } from "../data.js";

export function calendar() {
  const today = new Date(2024, 4, 15);
  const tasks = projects.flatMap((p) => p.tasks.map((t) => ({ ...t, project: p.name })));
  const due = groupBy(tasks, (t) => t.due);
  const months = [0, 1, 2].map((k) => addMonths(startOfMonth(today), k));
  return rendered(h(Page, { title: "Calendar" }, months.map((month) => {
    const days = eachDayOfInterval({ start: startOfWeek(startOfMonth(month)), end: endOfWeek(endOfMonth(month)) });
    return h("section", { key: format(month, "yyyy-MM") },
      h("h2", null, format(month, "MMMM yyyy")),
      h("ol", { className: "grid" }, days.map((day) => {
        const key = format(day, "yyyy-MM-dd"), items = due[key] || [];
        return h("li", { key, className: [isWeekend(day) && "weekend", !isSameMonth(day, month) && "outside"].filter(Boolean).join(" ") },
          h("time", { dateTime: key }, format(day, "d")),
          items.slice(0, 2).map((t) => h("span", { key: t.id, title: t.project },
            t.title, " ", isBefore(parseISO(t.due), today) ? `${differenceInCalendarDays(today, parseISO(t.due))}d late` : "")));
      })));
  })));
}
