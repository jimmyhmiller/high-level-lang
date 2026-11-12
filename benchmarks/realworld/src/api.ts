// The app's HTTP layer: axios with an adapter that answers from the seeded data, as a mock server
// would, and react-query hooks over it.
import axios, { type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios';
import qs from 'qs';
import { useQuery } from '@tanstack/react-query';
import { customers, orders, type Customer, type Order } from './data';

const routes: Record<string, (params: Record<string, unknown>) => unknown> = {
  '/customers': (params) => (params.region ? customers.filter((c) => c.region === params.region) : customers),
  '/orders': (params) => {
    const status = params.status as string | undefined;
    return status ? orders.filter((o) => o.status === status) : orders;
  },
  '/health': () => ({ ok: true, version: '2.4.1' }),
};

const mockAdapter: AxiosAdapter = async (config: InternalAxiosRequestConfig) => {
  const [path, query = ''] = (config.url ?? '').split('?');
  const params = { ...(qs.parse(query) as Record<string, unknown>), ...(config.params ?? {}) };
  const handler = routes[path];
  if (!handler) {
    return { data: { error: 'not found' }, status: 404, statusText: 'Not Found', headers: {}, config };
  }
  return { data: handler(params), status: 200, statusText: 'OK', headers: { 'content-type': 'application/json' }, config };
};

export const http = axios.create({
  baseURL: '',
  adapter: mockAdapter,
  paramsSerializer: { serialize: (params) => qs.stringify(params, { arrayFormat: 'brackets' }) },
});

http.interceptors.request.use((config) => {
  config.headers.set('X-Client', 'field-ops');
  return config;
});

export function useCustomers(region?: string) {
  return useQuery({
    queryKey: ['customers', region ?? 'all'],
    queryFn: async () => (await http.get<Customer[]>('/customers', { params: region ? { region } : {} })).data,
  });
}

export function useOrders(status?: string) {
  return useQuery({
    queryKey: ['orders', status ?? 'all'],
    queryFn: async () => (await http.get<Order[]>('/orders', { params: status ? { status } : {} })).data,
  });
}
