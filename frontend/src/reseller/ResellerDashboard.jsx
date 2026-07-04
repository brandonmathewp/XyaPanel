import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function ResellerDashboard() {
  const { logout } = useAuth();

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ marginBottom: 0 }}>Reseller Panel</h2>
        <button className="sm secondary" onClick={logout}>Logout</button>
      </div>

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
