// Revenue by region and month: recharts, Chart.js through react-chartjs-2, and d3 for formats and a
// sparkline, over orders fetched with react-query and summed with decimal.js.
import { useMemo } from 'react';
import { Card, CardContent, Grid, MenuItem, Select, Typography } from '@mui/material';
import { BarChart, Bar, CartesianGrid, Legend, Tooltip as ChartTooltip, XAxis, YAxis } from 'recharts';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend as JsLegend } from 'chart.js';
import { Line } from 'react-chartjs-2';
import * as d3 from 'd3';
import Decimal from 'decimal.js';
import { format, parseISO, startOfMonth } from 'date-fns';
import { groupBy, sortBy } from 'lodash-es';
import { useTranslation } from 'react-i18next';
import { useOrders } from '../api';
import { customerById, REGIONS } from '../data';
import { regionChosen, useAppDispatch, useAppSelector } from '../store';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, JsLegend);

const money = d3.format('$,.2f');

function Sparkline({ values }: { values: number[] }) {
  const x = d3.scaleLinear().domain([0, values.length - 1]).range([0, 160]);
  const [low, high] = d3.extent(values) as [number, number];
  const y = d3.scaleLinear().domain([low, high]).range([36, 4]);
  const path = d3.line<number>().x((_, i) => x(i)).y((v) => y(v)).curve(d3.curveMonotoneX)(values) ?? '';
  return (
    <svg width={160} height={40} role="img" aria-label="trend">
      <path d={path} fill="none" stroke="#1b4d89" strokeWidth={1.5} />
    </svg>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const region = useAppSelector((state) => state.ui.region);
  const { data: orders = [], isPending } = useOrders();

  const view = useMemo(() => {
    const kept = orders.filter((o) => o.status !== 'refunded' && (region === 'All' || customerById.get(o.customerId)?.region === region));
    const byRegion = REGIONS.map((name) => {
      const total = kept
        .filter((o) => customerById.get(o.customerId)?.region === name)
        .reduce((sum, o) => sum.plus(o.amount), new Decimal(0));
      return { region: name, revenue: total.toNumber() };
    });
    const months = groupBy(kept, (o) => format(startOfMonth(parseISO(o.date)), 'yyyy-MM'));
    const monthly = sortBy(Object.keys(months)).map((month) => ({
      month,
      revenue: months[month].reduce((sum, o) => sum.plus(o.amount), new Decimal(0)).toNumber(),
    }));
    const total = kept.reduce((sum, o) => sum.plus(o.amount), new Decimal(0));
    return { kept, byRegion, monthly, total };
  }, [orders, region]);

  if (isPending) return <Typography>Loading orders…</Typography>;

  return (
    <Grid container spacing={2}>
      <Grid size={12}>
        <Typography variant="h5">{t('dashboard.revenue')}</Typography>
        <Typography>
          {t('dashboard.orders', { count: view.kept.length })} · {money(view.total.toNumber())}
        </Typography>
        <Select size="small" value={region} onChange={(e) => dispatch(regionChosen(String(e.target.value)))}>
          {['All', ...REGIONS].map((r) => (
            <MenuItem key={r} value={r}>
              {r}
            </MenuItem>
          ))}
        </Select>
      </Grid>
      {view.byRegion.map((r) => (
        <Grid key={r.region} size={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="overline">{r.region}</Typography>
              <Typography variant="h6">{money(r.revenue)}</Typography>
            </CardContent>
          </Card>
        </Grid>
      ))}
      <Grid size={6}>
        <BarChart width={520} height={260} data={view.byRegion}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="region" />
          <YAxis tickFormatter={(v: number) => d3.format('.2s')(v)} />
          <ChartTooltip />
          <Legend />
          <Bar dataKey="revenue" fill="#1b4d89" isAnimationActive={false} />
        </BarChart>
      </Grid>
      <Grid size={6}>
        <Typography variant="subtitle1">{t('dashboard.monthly')}</Typography>
        <Line
          data={{
            labels: view.monthly.map((m) => m.month),
            datasets: [{ label: 'Revenue', data: view.monthly.map((m) => m.revenue), borderColor: '#c2185b', fill: false }],
          }}
          options={{ animation: false, responsive: false, plugins: { legend: { display: false } } }}
          width={520}
          height={260}
        />
        <Sparkline values={view.monthly.map((m) => m.revenue)} />
        <Typography variant="caption">
          Best month: {view.monthly.length ? d3.greatest(view.monthly, (m) => m.revenue)!.month : 'none'}
        </Typography>
      </Grid>
    </Grid>
  );
}
