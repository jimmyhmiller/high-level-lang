import { addDays, format, differenceInDays, parseISO, startOfMonth } from "date-fns";
const d = parseISO("2024-03-15T12:00:00Z");
console.log(format(addDays(d, 20), "yyyy-MM-dd"), differenceInDays(addDays(d, 9), d), format(startOfMonth(d), "yyyy-MM-dd"));
