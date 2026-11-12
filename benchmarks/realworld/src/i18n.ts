import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const en = {
  app: { title: 'Field Ops Console', loading: 'Loading…' },
  nav: {
    dashboard: 'Dashboard', customers: 'Customers', editor: 'Editor', forms: 'Forms', workflow: 'Workflow',
    graph: 'Graph', viewer: '3D', reports: 'Reports', motion: 'Motion',
  },
  dashboard: { revenue: 'Revenue by region', monthly: 'Monthly revenue', orders_one: '{{count}} order', orders_other: '{{count}} orders' },
  customers: { match_one: '{{count}} customer matches', match_other: '{{count}} customers match', search: 'Search customers' },
};

const fr = {
  app: { title: 'Console des opérations', loading: 'Chargement…' },
  nav: {
    dashboard: 'Tableau de bord', customers: 'Clients', editor: 'Éditeur', forms: 'Formulaires', workflow: 'Flux',
    graph: 'Graphe', viewer: '3D', reports: 'Rapports', motion: 'Animation',
  },
  dashboard: { revenue: 'Revenu par région', monthly: 'Revenu mensuel', orders_one: '{{count}} commande', orders_other: '{{count}} commandes' },
  customers: { match_one: '{{count}} client trouvé', match_other: '{{count}} clients trouvés', search: 'Rechercher' },
};

i18n.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  initAsync: false,
  resources: { en: { translation: en }, fr: { translation: fr } },
  interpolation: { escapeValue: false },
});

export default i18n;
