import moment from "moment";
const m = moment.utc("2021-03-14T01:59:26Z");
console.log(m.format("dddd, MMMM Do YYYY, h:mm:ss a"), m.clone().add(40, "days").format("L"), m.week(), m.isoWeekday(),
  moment.duration(123456789).humanize(), m.clone().endOf("quarter").toISOString(), moment.utc("2020-02-30").isValid(), m.dayOfYear());
