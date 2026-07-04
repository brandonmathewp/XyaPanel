import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import api from '../api';

export default function ResellerDashboard() {
  const { logout } = useAuth();
  const [balance, setBalance] = useState(null);
  const [stock, setStock] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.resellerStock().then(d => setStock(d.data || [])).catch(e => setError(e.message));
    fetch('/api/reseller/balance', { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
      .then(r => r.json()).then(d => setBalance(d.balance)).catch(() => {});
  }, []);

  const totalStock = stock.reduce((sum, s) => sum + s.quantity, 0);

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ marginBottom: 0 }}>Reseller Panel</h2>
        <button className="sm secondary" onClick={logout}>Logout</button>
      </div>

      <div className="card" style={{ background: 'linear-gradient(135deg, #2563eb, #1d4ed8)', color: 'white' }}>
        <div style={{ fontSize: '0.85rem', opacity: 0.85 }}>Balance</div>
        <div style={{ fontSize: '2rem', fontWeight: 700 }}>${balance !== null ? balance.toFixed(2) : '—'}</div>
      </div>

      <div className="card flex-between" style={{ marginTop: '0.75rem' }}>
        <div><strong>📦 Stock</strong><br /><small style={{ color: '#6b7280' }}>{totalStock} keys in inventory</small></div>
      </div>

      {stock.slice(0, 5).map(s => (
        <div key={s.product_id + s.duration} className="card flex-between" style={{ padding: '0.5rem 1rem' }}>
          <div>
            <span style={{ fontWeight: 600 }}>{s.product_name || s.product_id}</span>
            <span className="pill" style={{ marginLeft: 6 }}>{s.duration}</span>
          </div>
          <strong>{s.quantity}</strong>
        </div>
      ))}

      {error && <p style={{ color: '#dc2626', fontSize: '0.85rem' }}>{error}</p>}

      <Link to="/reseller/store">
        <div className="card flex-between">
          <div><strong>🛒 Store</strong><br /><small style={{ color: '#6b7280' }}>Browse &amp; purchase stock</small></div>
          <span style={{ fontSize: '1.5rem' }}>→</span>
        </div>
      </Link>

      <Link to="/reseller/keys">
        <div className="card flex-between">
          <div><strong>🔑 My Keys</strong><br /><small style={{ color: '#6b7280' }}>View generated licenses</small></div>
          <span style={{ fontSize: '1.5rem' }}>→</span>
        </div>
      </Link>

      <Link to="/reseller/ledger">
        <div className="card flex-between">
          <div><strong>📒 Ledger</strong><br /><small style={{ color: '#6b7280' }}>Transaction history</small></div>
          <span style={{ fontSize: '1.5rem' }}>→</span>
        </div>
      </Link>

      <div className="nav">
        <Link to="/reseller" className="active">🏠 Home</Link>
      </div>
    </div>
  );
}
