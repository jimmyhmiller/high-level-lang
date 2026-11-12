// Seeded sample data: every build of the app, by any bundler, shows the same customers and orders.
import { v5 as uuidv5 } from 'uuid';
import Decimal from 'decimal.js';
import { addDays, formatISO } from 'date-fns';

const NAMESPACE = '6f1c3c1e-9d4b-4d38-9b8e-2f4a0c7d5e11';

export function seeded(seed: number): () => number {
  let state = seed | 0;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const FIRST = ['Ada', 'Grace', 'Alan', 'Barbara', 'Edsger', 'Frances', 'Donald', 'Annie', 'Ken', 'Radia',
  'Leslie', 'Margaret', 'John', 'Hedy', 'Dennis', 'Shafi', 'Niklaus', 'Sophie', 'Tim', 'Jean'];
const LAST = ['Lovelace', 'Hopper', 'Turing', 'Liskov', 'Dijkstra', 'Allen', 'Knuth', 'Easley', 'Thompson',
  'Perlman', 'Lamport', 'Hamilton', 'McCarthy', 'Lamarr', 'Ritchie', 'Goldwasser', 'Wirth', 'Wilson', 'Berners-Lee', 'Sammet'];
const CITIES = [
  { city: 'Seattle', region: 'West', phone: '+1206555' },
  { city: 'Austin', region: 'South', phone: '+1512555' },
  { city: 'Boston', region: 'East', phone: '+1617555' },
  { city: 'Chicago', region: 'North', phone: '+1312555' },
  { city: 'Denver', region: 'West', phone: '+1303555' },
  { city: 'Atlanta', region: 'South', phone: '+1404555' },
  { city: 'New York', region: 'East', phone: '+1212555' },
  { city: 'Minneapolis', region: 'North', phone: '+1612555' },
];
export const REGIONS = ['North', 'South', 'East', 'West'] as const;
export const STATUSES = ['pending', 'paid', 'shipped', 'refunded'] as const;

export interface Customer {
  id: string;
  name: string;
  email: string;
  phone: string;
  city: string;
  region: string;
  joined: string;
}

export interface Order {
  id: string;
  customerId: string;
  date: string;
  amount: string;
  status: (typeof STATUSES)[number];
  items: number;
}

const START = new Date(Date.UTC(2025, 0, 1));

export function makeCustomers(count: number): Customer[] {
  const random = seeded(17);
  const out: Customer[] = [];
  for (let i = 0; i < count; i++) {
    const first = FIRST[Math.floor(random() * FIRST.length)];
    const last = LAST[Math.floor(random() * LAST.length)];
    const place = CITIES[Math.floor(random() * CITIES.length)];
    const bad = random() < 0.04;
    out.push({
      id: uuidv5('customer-' + i, NAMESPACE),
      name: `${first} ${last}`,
      email: bad ? `${first}.${last}@invalid` : `${first}.${last}${i}@example.com`.toLowerCase(),
      phone: place.phone + String(1000 + Math.floor(random() * 9000)),
      city: place.city,
      region: place.region,
      joined: formatISO(addDays(START, Math.floor(random() * 365)), { representation: 'date' }),
    });
  }
  return out;
}

export function makeOrders(customers: Customer[], count: number): Order[] {
  const random = seeded(99);
  const out: Order[] = [];
  for (let i = 0; i < count; i++) {
    const customer = customers[Math.floor(random() * customers.length)];
    const cents = 500 + Math.floor(random() * 250000);
    out.push({
      id: uuidv5('order-' + i, NAMESPACE),
      customerId: customer.id,
      date: formatISO(addDays(START, Math.floor(random() * 540)), { representation: 'date' }),
      amount: new Decimal(cents).dividedBy(100).toFixed(2),
      status: STATUSES[Math.floor(random() * STATUSES.length)],
      items: 1 + Math.floor(random() * 12),
    });
  }
  return out;
}

export const customers = makeCustomers(2000);
export const orders = makeOrders(customers, 6000);
export const customerById = new Map(customers.map((c) => [c.id, c]));
