import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';

export default function AdminProducts() {
  const [products, setProducts] = useState([]);
  const [total, setTotal] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ product_id: '', name: '', description: '', features: '' });
  const [msg, setMsg] = useState('');

  const load = async () => {
    try {
      const data = await api.listProducts();
      setProducts(data.data || []);
      setTotal(data.total || 0);
    } catch (e) { setMsg(e.message); }
  };

  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.createProduct({ ...form, features: form.features ? form.features.split(',').map(s => s.trim()) : [] });
      setShowForm(false);
      setForm({ product_id: '', name: '', description: '', features: '' });
      load();
    } catch (e) { setMsg(e.message); }
  };

  const del = async (id) => {
    if (!confirm(`Delete ${id}? All licenses must be removed first.`)) return;
    try { await api.deleteProduct(id); load(); } catch (e) { setMsg(e.message); }
  };

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: '0.75rem' }}>
        <h2 style={{ marginBottom: 0 }}>Products <span style={{ fontSize: '0.8rem', color: '#6b7280' }}>({total})</span></h2>
        <button className="sm" onClick={() => setShowForm(true)}>+ New</button>
      </div>

      {msg && <p style={{ color: '#dc2626', fontSize: '0.85rem' }}>{msg}</p>}

      {products.map(p => (
        <div key={p.product_id} className="card">
          <div className="flex-between">
            <div>
              <strong>{p.name}</strong>
              <span className="pill" style={{ marginLeft: 6 }}>{p.product_id}</span>
              {!p.store_enabled && <span className="pill" style={{ background: '#fee2e2', color: '#991b1b', marginLeft: 4 }}>Store Off</span>}
            </div>
            <button className="sm danger" onClick={() => del(p.product_id)}>Del</button>
          </div>
          {p.description && <p style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: '0.25rem' }}>{p.description}</p>}
          <div className="flex-row" style={{ flexWrap: 'wrap', marginTop: '0.25rem', gap: 4 }}>
            {(p.durations || []).map(d => (
              <span key={d.duration} className="pill">{d.duration} @ ${d.price}</span>
            ))}
          </div>
          <div className="flex-row" style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            <span>APK: {p.has_apk ? '✅' : '❌'}</span>
            <span>.so: {p.has_so ? '✅' : '❌'}</span>
          </div>
        </div>
      ))}

      {showForm && (
        <div className="modal-overlay" onClick={() => setShowForm(false)}>
          <div className="modal-sheet" onClick={e => e.stopPropagation()}>
            <h3>New Product</h3>
            <form onSubmit={create}>
              <input placeholder="Product ID (e.g. my-app)" value={form.product_id} onChange={e => setForm({ ...form, product_id: e.target.value })} required />
              <input placeholder="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
              <input placeholder="Description" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              <input placeholder="Features (comma-separated)" value={form.features} onChange={e => setForm({ ...form, features: e.target.value })} />
              <button type="submit">Create</button>
            </form>
          </div>
        </div>
      )}

      <div className="nav">
        <Link to="/admin">🏠</Link>
        <Link to="/admin/licenses">🔑</Link>
        <Link to="/admin/products" className="active">📦</Link>
        <Link to="/admin/invites">✉️</Link>
      </div>
    </div>
  );
}
