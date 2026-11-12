import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip } from "chart.js";
Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);
console.log(Object.keys(Chart.registry.controllers.items).join(","), Object.keys(Chart.registry.scales.items).join(","), Chart.defaults.plugins.tooltip.enabled);
