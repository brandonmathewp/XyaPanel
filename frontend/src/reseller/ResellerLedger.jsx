import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';

const typeColor = (t) => {
  const map = { credit: '#16a34a', purchase: '#dc2626', refund: '#f59e0b', key_generation: '#6b7280' };
  return map[t] || '#6b7280';
};

export default function ResellerLedger() {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [msg, setMsg] = useState('');

  const load = async () => {
    try {
      const params = new URLSearchParams({ page, page_size: 50 });
      const data = await api.resellerLedger(params.toString());
      setEntries(data.data || []);
      setTotal(data.total || 0);
    } catch (e) { setMsg(e.message); }
  };

  useEffect(() => { load(); }, [page]);

  return (
    <div className="page">
      <h2>Ledger</h2>
      {msg && <p style={{ color: '#dc2626', fontSize: '0.85rem' }}>{msg}</p>}

      {entries.map((e, i) => (
        <div key={i} className="card">
          <div className="flex-between">
            <span className="badge" style={{ background: typeColor(e.type), color: 'white' }}>{e.type}</span>
            <strong style={{ color: e.amount >= 0 ? '#16a34a' : '#dc2626' }}>
              {e.amount >= 0 ? '+' : ''}{e.amount.toFixed(2)}
            </strong>
          </div>
          <div className="flex-row" style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.25rem' }}>
            {e.product_id && <span>{e.product_id}</span>}
            {e.duration && <span>· {e.duration}</span>}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.15rem' }}>
            Balance: ${e.resulting_balance?.toFixed(2)} · {new Date(e.created_at).toLocaleDateString()}
          </div>
          {e.note && <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.15rem' }}>{e.note}</div>}
        </div>
      ))}

      {total > 50 && (
        <div className="flex-row" style={{ justifyContent: 'center' }}>
          <button className="sm secondary" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</button>
          <span>Page {page}</span>
          <button className="sm secondary" disabled={page * 50 >= total} onClick={() => setPage(p => p + 1)}>Next</button>
        </div>
      )}

      <div className="nav">
        <Link to="/reseller">🏠</Link>
        <Link to="/reseller/store">🛒</Link>
        <Link to="/reseller/keys">🔑</Link>
        <Link to="/reseller/ledger" className="active">📒</Link>
      </div>
    </div>
  );
}
