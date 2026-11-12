import { Chart, registerables, Colors, LinearScale, CategoryScale } from "chart.js";
Chart.register(...registerables);
const reg = Chart.registry;
console.log(["controllers","elements","plugins","scales"].map(k => k + ":" + Object.keys(reg[k].items).sort().join(",")).join("\n"));
console.log(typeof Colors.id, LinearScale.id, CategoryScale.id, JSON.stringify(Chart.defaults.font));
