// A searchable customer list: Fuse fuzzy search behind a lodash debounce, a react-window virtual
// list, phone numbers formatted by libphonenumber-js and emails checked by validator.
import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { Alert, Box, TextField, Typography } from '@mui/material';
import { List, type RowComponentProps } from 'react-window';
import Fuse from 'fuse.js';
import { debounce } from 'lodash-es';
import { parsePhoneNumberFromString } from 'libphonenumber-js';
import validator from 'validator';
import clsx from 'clsx';
import { useTranslation } from 'react-i18next';
import { useCustomers } from '../api';
import type { Customer } from '../data';

function formatPhone(raw: string): string {
  return parsePhoneNumberFromString(raw)?.formatInternational() ?? raw;
}

function Row({ index, style, rows }: RowComponentProps<{ rows: Customer[] }>) {
  const c = rows[index];
  const valid = validator.isEmail(c.email);
  return (
    <div style={style as CSSProperties} className={clsx('row', { invalid: !valid, odd: index % 2 === 1 })}>
      <strong>{c.name}</strong> · {c.city} · {formatPhone(c.phone)} · {valid ? c.email : `${c.email} (invalid)`}
    </div>
  );
}

export default function Customers() {
  const { t } = useTranslation();
  const { data = [], isPending } = useCustomers();
  const [input, setInput] = useState('');
  const [query, setQuery] = useState('');
  const update = useMemo(() => debounce((value: string) => setQuery(value), 120), []);
  useEffect(() => () => update.cancel(), [update]);

  const fuse = useMemo(() => new Fuse(data, { keys: ['name', 'city', 'email'], threshold: 0.3, ignoreLocation: true }), [data]);
  const rows = useMemo(() => (query ? fuse.search(query).map((r) => r.item) : data), [fuse, query, data]);
  const invalid = useMemo(() => data.filter((c) => !validator.isEmail(c.email)).length, [data]);

  if (isPending) return <Typography>Loading customers…</Typography>;
  return (
    <Box>
      <TextField
        name="search"
        size="small"
        label={t('customers.search')}
        value={input}
        onChange={(e) => {
          setInput(e.target.value);
          update(e.target.value);
        }}
      />
      <Typography sx={{ my: 1 }}>{t('customers.match', { count: rows.length })}</Typography>
      {invalid > 0 && <Alert severity="warning">{invalid} customers have an invalid email address</Alert>}
      <List rowComponent={Row} rowCount={rows.length} rowHeight={28} rowProps={{ rows }} style={{ height: 420 }} />
    </Box>
  );
}
