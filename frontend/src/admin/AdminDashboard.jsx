import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function AdminDashboard() {
  const { logout } = useAuth();

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ marginBottom: 0 }}>Admin Panel</h2>
        <button className="sm secondary" onClick={logout}>Logout</button>
      </div>

      <Link to="/admin/licenses">
        <div className="card flex-between">
          <div><strong>🔑 Licenses</strong><br /><small style={{ color: '#6b7280' }}>Generate, revoke, manage keys</small></div>
          <span style={{ fontSize: '1.5rem' }}>→</span>
        </div>
      </Link>

      <Link to="/admin/products">
        <div className="card flex-between">
          <div><strong>📦 Products</strong><br /><small style={{ color: '#6b7280' }}>Manage products &amp; artifacts</small></div>
          <span style={{ fontSize: '1.5rem' }}>→</span>
        </div>
      </Link>

      <Link to="/admin/invites">
        <div className="card flex-between">
          <div><strong>✉️ Invite Codes</strong><br /><small style={{ color: '#6b7280' }}>Generate reseller invites</small></div>
          <span style={{ fontSize: '1.5rem' }}>→</span>
        </div>
      </Link>

      <div className="nav">
        <Link to="/admin" className="active">🏠 Home</Link>
      </div>
    </div>
  );
}
