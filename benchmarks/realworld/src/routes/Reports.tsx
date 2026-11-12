// A monthly report: orders grouped with Ramda and lodash, exported to CSV by Papa Parse and read
// back, dates shown three ways (Moment, Luxon, Day.js with time zones), and a share link by qs.
import { useMemo } from 'react';
import { Box, Link, List, ListItem, Typography } from '@mui/material';
import * as R from 'ramda';
import chunk from 'lodash/chunk';
import sortBy from 'lodash/sortBy';
import Papa from 'papaparse';
import moment from 'moment';
import { DateTime } from 'luxon';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import qs from 'qs';
import Decimal from 'decimal.js';
import { customerById, orders, type Order } from '../data';

dayjs.extend(utc);
dayjs.extend(timezone);

const REPORT_AT = '2026-03-31T17:45:00Z';

const byStatus = R.pipe(
  R.filter((o: Order) => o.items > 0),
  R.countBy((o: Order) => o.status),
);

export default function Reports() {
  const report = useMemo(() => {
    const march = orders.filter((o) => o.date.startsWith('2026-03'));
    const rows = sortBy(march, ['date', 'id']).map((o) => ({
      date: o.date,
      customer: customerById.get(o.customerId)?.name ?? 'unknown',
      status: o.status,
      amount: o.amount,
    }));
    const csv = Papa.unparse(rows);
    const parsed = Papa.parse<Record<string, string>>(csv, { header: true, skipEmptyLines: true });
    const total = parsed.data.reduce((sum, r) => sum.plus(r.amount), new Decimal(0));
    const pages = chunk(parsed.data, 25).length;
    const counts = byStatus(march);
    const share = qs.stringify({ report: 'monthly', month: '2026-03', status: Object.keys(counts).sort(), page: 1 }, { arrayFormat: 'brackets', encode: false });
    return { rows: parsed.data.length, bytes: csv.length, total: total.toFixed(2), pages, counts, share };
  }, []);

  const when = {
    moment: moment.utc(REPORT_AT).format('dddd, MMMM Do YYYY, h:mm a'),
    luxon: DateTime.fromISO(REPORT_AT, { zone: 'utc' }).setZone('America/New_York').toFormat("ccc d LLL yyyy HH:mm 'New York'"),
    dayjs: dayjs(REPORT_AT).tz('Asia/Tokyo').format('YYYY-MM-DD HH:mm [Tokyo]'),
  };

  return (
    <Box>
      <Typography variant="h5">Monthly report</Typography>
      <Typography>
        {report.rows} orders in March 2026 · {report.total} total · {report.pages} pages · {report.bytes} bytes of CSV
      </Typography>
      <List dense>
        {Object.entries(report.counts)
          .sort()
          .map(([status, n]) => (
            <ListItem key={status}>
              {status}: {n}
            </ListItem>
          ))}
      </List>
      <Typography>Prepared {when.moment}</Typography>
      <Typography>Also {when.luxon} · {when.dayjs}</Typography>
      <Link href={`/reports?${report.share}`}>Share link: ?{report.share}</Link>
      <Typography>Report ready</Typography>
    </Box>
  );
}
