// Accounts over GraphQL: a schema executed in the page by graphql-js, behind an Apollo Client link,
// read with Apollo's useQuery and cached by its InMemoryCache.
import { useMemo } from 'react';
import { Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { ApolloClient, ApolloLink, InMemoryCache, gql } from '@apollo/client';
import { ApolloProvider, useQuery } from '@apollo/client/react';
import { Observable } from 'rxjs';
import { buildSchema, graphql, print } from 'graphql';
import Decimal from 'decimal.js';
import { customers, orders } from '../data';

const schema = buildSchema(`
  type Account { id: ID!, name: String!, city: String!, orders: Int!, spend: String! }
  type Query { topAccounts(limit: Int!, city: String): [Account!]! }
`);

const rootValue = {
  topAccounts({ limit, city }: { limit: number; city?: string }) {
    const spend = new Map<string, { count: number; total: Decimal }>();
    for (const o of orders) {
      if (o.status === 'refunded') continue;
      const s = spend.get(o.customerId) ?? { count: 0, total: new Decimal(0) };
      s.count += 1;
      s.total = s.total.plus(o.amount);
      spend.set(o.customerId, s);
    }
    return customers
      .filter((c) => !city || c.city === city)
      .map((c) => ({ ...c, orders: spend.get(c.id)?.count ?? 0, total: spend.get(c.id)?.total ?? new Decimal(0) }))
      .sort((a, b) => b.total.comparedTo(a.total) || a.id.localeCompare(b.id))
      .slice(0, limit)
      .map((c) => ({ id: c.id, name: c.name, city: c.city, orders: c.orders, spend: c.total.toFixed(2) }));
  },
};

const local = new ApolloLink(
  (operation) =>
    new Observable((observer) => {
      graphql({ schema, source: print(operation.query), variableValues: operation.variables, rootValue })
        .then((result) => {
          observer.next(result as never);
          observer.complete();
        })
        .catch((error) => observer.error(error));
    }),
);

const TOP = gql`
  query Top($limit: Int!) {
    topAccounts(limit: $limit) {
      id
      name
      city
      orders
      spend
    }
  }
`;

interface Top {
  topAccounts: { id: string; name: string; city: string; orders: number; spend: string }[];
}

function Accounts() {
  const { data, loading, error } = useQuery<Top>(TOP, { variables: { limit: 8 } });
  if (loading) return <Typography>Querying…</Typography>;
  if (error) throw error;
  return (
    <>
      <Typography variant="h5">Top accounts</Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>City</TableCell>
            <TableCell align="right">Orders</TableCell>
            <TableCell align="right">Spend</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data!.topAccounts.map((a) => (
            <TableRow key={a.id}>
              <TableCell>{a.name}</TableCell>
              <TableCell>{a.city}</TableCell>
              <TableCell align="right">{a.orders}</TableCell>
              <TableCell align="right">{a.spend}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}

export default function Graph() {
  const client = useMemo(() => new ApolloClient({ link: local, cache: new InMemoryCache() }), []);
  return (
    <ApolloProvider client={client}>
      <Accounts />
    </ApolloProvider>
  );
}
