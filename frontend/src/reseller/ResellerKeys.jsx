import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';

const statusBadge = (s) => {
  const map = { active: 'badge-active', pending: 'badge-pending', paused: 'badge-paused', revoked: 'badge-revoked', expired: 'badge-expired', watermark_failed: 'badge-wm_fail' };
  return map[s] || '';
};

export default function ResellerKeys() {
  const [keys, setKeys] = useState([]);
  const [total, setTotal] = useState(0);
  const [showGen, setShowGen] = useState(false);
  const [genForm, setGenForm] = useState({ product_id: '', duration: '1_month', customer: '', features: '' });
  const [msg, setMsg] = useState('');

  const load = async () => {
    try {
      const data = await api.resellerKeys();
      setKeys(data.data || []);
      setTotal(data.total || 0);
    } catch (e) { setMsg(e.message); }
  };

  useEffect(() => { load(); }, []);

  const generate = async (e) => {
    e.preventDefault();
    try {
      await api.generateResellerKey({ ...genForm, features: genForm.features ? genForm.features.split(',').map(s => s.trim()) : [], duration: genForm.duration });
      setShowGen(false);
      setMsg('Key generated!');
      load();
    } catch (e) { setMsg(e.message); }
  };

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: '0.75rem' }}>
        <h2 style={{ marginBottom: 0 }}>My Keys {total > 0 && <span style={{ fontSize: '0.8rem', color: '#6b7280' }}>({total})</span>}</h2>
        <button className="sm" onClick={() => setShowGen(true)}>+ Generate</button>
      </div>

      {msg && <p style={{ color: '#16a34a', fontSize: '0.85rem' }}>{msg}</p>}

      {keys.map(k => (
        <div key={k.license_key} className="card">
          <div className="flex-between">
            <span className={`badge ${statusBadge(k.status)}`}>{k.status}</span>
          </div>
          <div style={{ fontFamily: 'monospace', fontSize: '0.8rem', marginTop: '0.5rem', wordBreak: 'break-all' }}>{k.license_key}</div>
          <div className="flex-row" style={{ marginTop: '0.25rem', fontSize: '0.8rem', color: '#6b7280' }}>
            <span>{k.product_id} · {k.duration}</span>
            {k.hwid && <span>· HWID: {k.hwid.slice(0, 12)}…</span>}
          </div>
        </div>
      ))}

      {showGen && (
        <div className="modal-overlay" onClick={() => setShowGen(false)}>
          <div className="modal-sheet" onClick={e => e.stopPropagation()}>
            <h3>Generate Key from Stock</h3>
            <form onSubmit={generate}>
              <input placeholder="Product ID" value={genForm.product_id} onChange={e => setGenForm({ ...genForm, product_id: e.target.value })} required />
              <select value={genForm.duration} onChange={e => setGenForm({ ...genForm, duration: e.target.value })}>
                {['2_hours','1_day','3_days','1_week','1_month','2_months','6_months','1_year','lifetime'].map(d => <option key={d} value={d}>{d}</option>)}
              </select>
              <input placeholder="Customer (optional)" value={genForm.customer} onChange={e => setGenForm({ ...genForm, customer: e.target.value })} />
              <input placeholder="Features (comma-separated)" value={genForm.features} onChange={e => setGenForm({ ...genForm, features: e.target.value })} />
              <button type="submit">Generate Key</button>
            </form>
          </div>
        </div>
      )}

      <div className="nav">
        <Link to="/reseller">🏠</Link>
        <Link to="/reseller/store">🛒</Link>
        <Link to="/reseller/keys" className="active">🔑</Link>
        <Link to="/reseller/ledger">📒</Link>
      </div>
    </div>
  );
}
