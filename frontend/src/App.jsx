import { useCallback, useMemo, useState } from 'react';
import './App.css';

const defaultBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

const endpointGroups = [
  {
    title: 'Campaign Service (Port 8005)',
    description: 'CRUD for campaign lifecycle.',
    endpoints: [
      {
        id: 'campaign-list',
        title: 'List Campaigns',
        description: 'GET /api/v1/campaigns',
        method: 'GET',
        path: '/api/v1/campaigns',
      },
      {
        id: 'campaign-get',
        title: 'Get Campaign',
        description: 'GET /api/v1/campaigns/{id}',
        method: 'GET',
        path: '/api/v1/campaigns/{id}',
        fields: [
          { name: 'id', label: 'Campaign ID', required: true, location: 'path' },
        ],
      },
      {
        id: 'campaign-create',
        title: 'Create Campaign',
        description: 'POST /api/v1/campaigns',
        method: 'POST',
        path: '/api/v1/campaigns',
        fields: [
          { name: 'title', label: 'Title', required: true },
          { name: 'description', label: 'Description', type: 'textarea' },
          { name: 'goal_amount', label: 'Goal Amount', type: 'number', required: true },
          { name: 'currency', label: 'Currency', defaultValue: 'USD' },
          { name: 'status', label: 'Status', defaultValue: 'ACTIVE' },
        ],
      },
      {
        id: 'campaign-update',
        title: 'Update Campaign',
        description: 'PATCH /api/v1/campaigns/{id}',
        method: 'PATCH',
        path: '/api/v1/campaigns/{id}',
        fields: [
          { name: 'id', label: 'Campaign ID', required: true, location: 'path' },
          { name: 'title', label: 'Title' },
          { name: 'status', label: 'Status' },
          { name: 'goal_amount', label: 'Goal Amount', type: 'number' },
        ],
      },
      {
        id: 'campaign-delete',
        title: 'Delete Campaign',
        description: 'DELETE /api/v1/campaigns/{id}',
        method: 'DELETE',
        path: '/api/v1/campaigns/{id}',
        fields: [
          { name: 'id', label: 'Campaign ID', required: true, location: 'path' },
        ],
      },
    ],
  },
  {
    title: 'Donation Service (Port 8001)',
    description: 'Handles pledges & donor history.',
    endpoints: [
      {
        id: 'donation-create',
        title: 'Create Donation',
        description: 'POST /api/v1/donations',
        method: 'POST',
        path: '/api/v1/donations',
        fields: [
          { name: 'campaign_id', label: 'Campaign ID', required: true },
          { name: 'donor_email', label: 'Donor Email', type: 'email', required: true },
          { name: 'amount', label: 'Amount', type: 'number', required: true },
          { name: 'currency', label: 'Currency', defaultValue: 'USD' },
        ],
      },
      {
        id: 'donation-get',
        title: 'Get Donation',
        description: 'GET /api/v1/donations/{id}',
        method: 'GET',
        path: '/api/v1/donations/{id}',
        fields: [
          { name: 'id', label: 'Donation ID', required: true, location: 'path' },
        ],
      },
      {
        id: 'donation-history',
        title: 'Donation History',
        description: 'GET /api/v1/donations/history',
        method: 'GET',
        path: '/api/v1/donations/history',
        fields: [
          { name: 'donor_email', label: 'Donor Email', location: 'query' },
        ],
      },
    ],
  },
  {
    title: 'Payment Service (Port 8002)',
    description: 'Payment intents, idempotent webhooks, refunds.',
    endpoints: [
      {
        id: 'payment-intent',
        title: 'Create Payment Intent',
        description: 'POST /api/v1/payments/intent',
        method: 'POST',
        path: '/api/v1/payments/intent',
        fields: [
          { name: 'donation_id', label: 'Donation ID', required: true },
          { name: 'amount', label: 'Amount', type: 'number', required: true },
          { name: 'currency', label: 'Currency', defaultValue: 'USD' },
          { name: 'gateway', label: 'Gateway', defaultValue: 'stripe' },
        ],
      },
      {
        id: 'payment-webhook',
        title: 'Webhook (Idempotent)',
        description: 'POST /api/v1/payments/webhook',
        method: 'POST',
        path: '/api/v1/payments/webhook',
        fields: [
          {
            name: 'x_idempotency_key',
            label: 'X-Idempotency-Key',
            location: 'header',
            headerName: 'X-Idempotency-Key',
          },
          { name: 'event_type', label: 'Event Type', defaultValue: 'payment.succeeded' },
          { name: 'payment_intent_id', label: 'Payment Intent ID', required: true },
          { name: 'status', label: 'Status', defaultValue: 'CAPTURED' },
          {
            name: 'timestamp',
            label: 'Timestamp',
            defaultValue: new Date().toISOString(),
          },
        ],
      },
      {
        id: 'payment-get',
        title: 'Get Payment',
        description: 'GET /api/v1/payments/{id}',
        method: 'GET',
        path: '/api/v1/payments/{id}',
        fields: [
          { name: 'id', label: 'Payment ID', required: true, location: 'path' },
        ],
      },
      {
        id: 'payment-refund',
        title: 'Refund Payment',
        description: 'POST /api/v1/payments/{id}/refund',
        method: 'POST',
        path: '/api/v1/payments/{id}/refund',
        fields: [
          { name: 'id', label: 'Payment ID', required: true, location: 'path' },
          { name: 'amount', label: 'Amount', type: 'number' },
          { name: 'reason', label: 'Reason' },
        ],
      },
    ],
  },
  {
    title: 'Totals Service (Port 8003)',
    description: 'Multi-level caching for campaign totals.',
    endpoints: [
      {
        id: 'totals-cached',
        title: 'Cached Totals',
        description: 'GET /api/v1/totals/campaigns/{id}',
        method: 'GET',
        path: '/api/v1/totals/campaigns/{id}',
        fields: [
          { name: 'id', label: 'Campaign ID', required: true, location: 'path' },
          {
            name: 'realtime',
            label: 'Realtime (?realtime=true)',
            type: 'checkbox',
            location: 'query',
            queryName: 'realtime',
            trueValue: 'true',
          },
        ],
      },
      {
        id: 'totals-refresh',
        title: 'Refresh Totals Cache',
        description: 'POST /api/v1/totals/refresh',
        method: 'POST',
        path: '/api/v1/totals/refresh',
        fields: [
          { name: 'campaign_id', label: 'Campaign ID (optional)' },
        ],
      },
    ],
  },
  {
    title: 'Bank Service (Port 8006)',
    description: 'Ledger-backed accounts & transfers.',
    endpoints: [
      {
        id: 'bank-account-create',
        title: 'Create Bank Account',
        description: 'POST /api/v1/bank/accounts',
        method: 'POST',
        path: '/api/v1/bank/accounts',
        fields: [
          { name: 'user_id', label: 'User ID', required: true },
          { name: 'account_holder_name', label: 'Account Holder', required: true },
          { name: 'email', label: 'Email', type: 'email', required: true },
          { name: 'initial_deposit', label: 'Initial Deposit', type: 'number' },
          { name: 'currency', label: 'Currency', defaultValue: 'USD' },
        ],
      },
      {
        id: 'bank-account-get',
        title: 'Get Bank Account',
        description: 'GET /api/v1/bank/accounts/{number}',
        method: 'GET',
        path: '/api/v1/bank/accounts/{number}',
        fields: [
          { name: 'number', label: 'Account Number', required: true, location: 'path' },
        ],
      },
      {
        id: 'bank-transfer',
        title: 'Create Transfer',
        description: 'POST /api/v1/bank/transfers',
        method: 'POST',
        path: '/api/v1/bank/transfers',
        fields: [
          { name: 'from_account_id', label: 'From Account ID', required: true },
          { name: 'to_account_id', label: 'To Account ID', required: true },
          { name: 'amount', label: 'Amount', type: 'number', required: true },
          { name: 'currency', label: 'Currency', defaultValue: 'USD' },
          { name: 'reference', label: 'Reference' },
        ],
      },
      {
        id: 'bank-transactions',
        title: 'Account Transactions',
        description: 'GET /api/v1/bank/accounts/{number}/transactions',
        method: 'GET',
        path: '/api/v1/bank/accounts/{number}/transactions',
        fields: [
          { name: 'number', label: 'Account Number', required: true, location: 'path' },
        ],
      },
    ],
  },
  {
    title: 'Admin Service (Port 8007)',
    description: 'Operational dashboards & system health (JWT required).',
    endpoints: [
      {
        id: 'admin-login',
        title: 'Admin Login',
        description: 'POST /api/v1/admin/auth/login',
        method: 'POST',
        path: '/api/v1/admin/auth/login',
        fields: [
          { name: 'email', label: 'Email', type: 'email', required: true },
          { name: 'password', label: 'Password', type: 'password', required: true },
        ],
      },
      {
        id: 'admin-dashboard',
        title: 'Dashboard Metrics',
        description: 'GET /api/v1/admin/dashboard',
        method: 'GET',
        path: '/api/v1/admin/dashboard',
        fields: [
          {
            name: 'authorization',
            label: 'Authorization Header',
            placeholder: 'Bearer <token>',
            location: 'header',
            headerName: 'Authorization',
            required: true,
          },
        ],
      },
      {
        id: 'admin-health',
        title: 'System Health',
        description: 'GET /api/v1/admin/system/health',
        method: 'GET',
        path: '/api/v1/admin/system/health',
        fields: [
          {
            name: 'authorization',
            label: 'Authorization Header',
            placeholder: 'Bearer <token>',
            location: 'header',
            headerName: 'Authorization',
            required: true,
          },
        ],
      },
      {
        id: 'admin-donations',
        title: 'All Donations (Admin)',
        description: 'GET /api/v1/admin/donations',
        method: 'GET',
        path: '/api/v1/admin/donations',
        fields: [
          {
            name: 'authorization',
            label: 'Authorization Header',
            placeholder: 'Bearer <token>',
            location: 'header',
            headerName: 'Authorization',
            required: true,
          },
        ],
      },
    ],
  },
  {
    title: 'Platform Utilities',
    description: 'Applies to every service.',
    endpoints: [
      {
        id: 'service-health',
        title: 'Service Health',
        description: 'GET /health',
        method: 'GET',
        path: '/health',
      },
      {
        id: 'service-metrics',
        title: 'Prometheus Metrics',
        description: 'GET /metrics',
        method: 'GET',
        path: '/metrics',
        expectText: true,
      },
    ],
  },
];

const formatResponse = (payload) => {
  if (!payload && payload !== 0) {
    return 'Awaiting response...';
  }
  if (typeof payload === 'string') {
    return payload;
  }
  return JSON.stringify(payload, null, 2);
};

const buildInitialValues = (fields = []) =>
  fields.reduce((acc, field) => {
    if (field.type === 'checkbox') {
      acc[field.name] = field.defaultValue ?? false;
    } else {
      acc[field.name] = field.defaultValue ?? '';
    }
    return acc;
  }, {});

const resolvePath = (path, key, value) => path.replace(new RegExp(`{${key}}`, 'g'), encodeURIComponent(value ?? ''));

const convertValue = (field, value) => {
  if (field?.parse) return field.parse(value);
  if (field?.type === 'number') {
    if (value === '' || value === null || value === undefined) return undefined;
    return Number(value);
  }
  if (field?.type === 'checkbox') {
    return Boolean(value);
  }
  return value;
};

const buildRequest = (config, values) => {
  let interpolatedPath = config.path;
  const body = {};
  const query = new URLSearchParams();
  const headers = {};

  (config.fields || []).forEach((field) => {
    const rawValue = values[field.name];
    const value = convertValue(field, rawValue);

    if (field.location === 'path') {
      interpolatedPath = resolvePath(interpolatedPath, field.name, value);
      return;
    }
    if (field.location === 'query') {
      if (value !== '' && value !== undefined && value !== false) {
        query.append(field.queryName ?? field.name, field.trueValue && value === true ? field.trueValue : value);
      }
      return;
    }
    if (field.location === 'header') {
      if (value) {
        headers[field.headerName ?? field.name] = value;
      }
      return;
    }
    if (value !== '' && value !== undefined) {
      body[field.bodyName ?? field.name] = value;
    }
  });

  const queryString = query.toString();
  const url = `${interpolatedPath}${queryString ? `?${queryString}` : ''}`;
  const hasBody = config.method !== 'GET' && Object.keys(body).length > 0;

  return {
    url,
    headers,
    body: hasBody ? body : undefined,
  };
};

function EndpointTester({ config, state, onSend }) {
  const [values, setValues] = useState(() => buildInitialValues(config.fields));

  const handleChange = (field) => (event) => {
    const value = field.type === 'checkbox' ? event.target.checked : event.target.value;
    setValues((prev) => ({ ...prev, [field.name]: value }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    onSend(config, values);
  };

  const triggerButton = (
    <button type={config.fields?.length ? 'submit' : 'button'} onClick={config.fields?.length ? undefined : () => onSend(config, values)} disabled={state?.loading}>
      {state?.loading ? 'Sending…' : config.cta ?? 'Send request'}
    </button>
  );

  return (
    <section className="panel" id={config.id}>
      <div className="panel-title">
        <div>
          <h3>{config.title}</h3>
          <p>{config.description}</p>
          <code>{config.method} {config.path}</code>
        </div>
        {!config.fields?.length && triggerButton}
      </div>
      {config.fields?.length ? (
        <form className="form-grid" onSubmit={handleSubmit}>
          {config.fields.map((field) =>
            field.type === 'checkbox' ? (
              <label key={field.name} className="toggle">
                <input
                  type="checkbox"
                  checked={Boolean(values[field.name])}
                  onChange={handleChange(field)}
                  required={field.required}
                />
                <span>{field.label}</span>
              </label>
            ) : (
              <label key={field.name} className="field">
                <span>{field.label}</span>
                {field.type === 'textarea' ? (
                  <textarea
                    value={values[field.name]}
                    onChange={handleChange(field)}
                    placeholder={field.placeholder}
                    required={field.required}
                  />
                ) : (
                  <input
                    type={field.type || 'text'}
                    value={values[field.name]}
                    onChange={handleChange(field)}
                    placeholder={field.placeholder}
                    required={field.required}
                  />
                )}
                {field.hint && <small>{field.hint}</small>}
              </label>
            ),
          )}
          {triggerButton}
        </form>
      ) : null}
      <pre className="response">
        {state?.error ? `Error: ${state.error}` : formatResponse(state?.data)}
      </pre>
    </section>
  );
}

function App() {
  const [baseUrl, setBaseUrl] = useState(defaultBaseUrl);
  const [results, setResults] = useState({});

  const apiBase = useMemo(() => baseUrl.replace(/\/$/, ''), [baseUrl]);

  const callApi = useCallback(async (config, values = {}) => {
    setResults((prev) => ({ ...prev, [config.id]: { loading: true, data: prev[config.id]?.data ?? null, error: null } }));
    try {
      const { url, body, headers } = buildRequest(config, values);
      const response = await fetch(`${apiBase}${url}`, {
        method: config.method,
        headers: {
          Accept: config.expectText ? 'text/plain' : 'application/json',
          ...(body ? { 'Content-Type': 'application/json' } : {}),
          ...headers,
        },
        body: body ? JSON.stringify(body) : undefined,
      });

      const raw = await response.text();
      const payload = config.expectText
        ? raw
        : (() => {
            if (!raw) return null;
            try {
              return JSON.parse(raw);
            } catch {
              return raw;
            }
          })();

      if (!response.ok) {
        throw new Error(
          typeof payload === 'string' ? payload : payload?.message || response.statusText || 'Request failed',
        );
      }

      setResults((prev) => ({ ...prev, [config.id]: { loading: false, data: payload, error: null } }));
    } catch (error) {
      setResults((prev) => ({ ...prev, [config.id]: { loading: false, data: null, error: error.message } }));
    }
  }, [apiBase]);

  return (
    <main className="layout">
      <section className="hero">
        <p className="eyebrow">CareForAll Platform</p>
        <h1>CareForAll API Console</h1>
        <p>Use the sections below to call each service endpoint from a single lightweight interface.</p>
      </section>

      <section className="panel">
        <h2>Environment</h2>
        <label className="field">
          <span>API Base URL</span>
          <input
            type="text"
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            placeholder="http://localhost:8000"
          />
        </label>
        <p className="hint">
          Default matches the API Gateway from the docs. Switch to a direct service URL if you bypass Nginx.
        </p>
      </section>

      {endpointGroups.map((group) => (
        <section key={group.title} className="group">
          <div className="group-header">
            <h2>{group.title}</h2>
            <p>{group.description}</p>
          </div>
          {group.endpoints.map((endpoint) => (
            <EndpointTester
              key={endpoint.id}
              config={endpoint}
              state={results[endpoint.id]}
              onSend={callApi}
            />
          ))}
        </section>
      ))}
    </main>
  );
}

export default App;

