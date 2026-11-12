import { Chart, LineController, LineElement, PointElement, TimeScale, Filler, Legend, Colors } from "chart.js";
Chart.register(LineController, LineElement, PointElement, Filler, Legend, Colors);
console.log(Object.keys(Chart.registry.plugins.items).join(","), Object.keys(Chart.registry.elements.items).join(","), typeof TimeScale, Chart.defaults.elements.line.tension);
