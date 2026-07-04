import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';

const statusBadge = (s) => {
  const map = { active: 'badge-active', pending: 'badge-pending', paused: 'badge-paused', revoked: 'badge-revoked', expired: 'badge-expired', watermark_failed: 'badge-wm_fail' };
  return map[s] || '';
};

export default function AdminLicenses() {
  const [licenses, setLicenses] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState('');
  const [showGen, setShowGen] = useState(false);
  const [genForm, setGenForm] = useState({ product_id: '', duration: '1_month', features: '' });
  const [msg, setMsg] = useState('');

  const load = async () => {
    try {
      const params = new URLSearchParams({ page, page_size: 20 });
      if (filter) params.set('status', filter);
      if (filter === 'flagged') { params.delete('status'); params.set('flagged_for_review', 'true'); }
      const data = await api.listLicenses(params.toString());
      setLicenses(data.data || []);
      setTotal(data.total || 0);
    } catch (e) { setMsg(e.message); }
  };

  useEffect(() => { load(); }, [page, filter]);

  const handleAction = async (key, action) => {
    try {
      if (action === 'revoke') await api.revokeLicense(key);
      else if (action === 'pause') await api.pauseLicense(key);
      else if (action === 'resume') await api.resumeLicense(key);
      load();
    } catch (e) { setMsg(e.message); }
  };

  const generate = async (e) => {
    e.preventDefault();
    try {
      await api.generateLicense({ ...genForm, features: genForm.features ? genForm.features.split(',').map(s => s.trim()) : [], duration: genForm.duration });
      setShowGen(false);
      setMsg('License generated!');
      load();
    } catch (e) { setMsg(e.message); }
  };

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: '0.75rem' }}>
        <h2 style={{ marginBottom: 0 }}>Licenses {total > 0 && <span style={{ fontSize: '0.8rem', color: '#6b7280' }}>({total})</span>}</h2>
        <button className="sm" onClick={() => setShowGen(true)}>+ Generate</button>
      </div>

      <div className="flex-row" style={{ marginBottom: '0.75rem' }}>
        <select value={filter} onChange={e => { setFilter(e.target.value); setPage(1); }} style={{ width: 'auto', marginBottom: 0 }}>
          <option value="">All</option>
          <option value="active">Active</option>
          <option value="pending">Pending</option>
          <option value="paused">Paused</option>
          <option value="revoked">Revoked</option>
          <option value="watermark_failed">WM Failed</option>
          <option value="flagged">⚠️ Flagged</option>
        </select>
      </div>

      {msg && <p style={{ color: '#16a34a', fontSize: '0.85rem' }}>{msg}</p>}

      {licenses.map(l => (
        <div key={l.license_key} className="card">
          <div className="flex-between">
            <div>
              <span className={`badge ${statusBadge(l.status)}`}>{l.status}</span>
              {l.flagged_for_review && <span className="badge" style={{ marginLeft: 4, background: '#fef3c7', color: '#92400e' }}>⚠️ Review</span>}
            </div>
            <div className="flex-row">
              {l.status === 'active' && <button className="sm secondary" onClick={() => handleAction(l.license_key, 'pause')}>Pause</button>}
              {l.status === 'paused' && <button className="sm success" onClick={() => handleAction(l.license_key, 'resume')}>Resume</button>}
              {l.status !== 'revoked' && <button className="sm danger" onClick={() => handleAction(l.license_key, 'revoke')}>Revoke</button>}
            </div>
          </div>
          <div style={{ fontFamily: 'monospace', fontSize: '0.8rem', marginTop: '0.5rem', wordBreak: 'break-all' }}>{l.license_key}</div>
          <div className="flex-row" style={{ marginTop: '0.25rem', fontSize: '0.8rem', color: '#6b7280' }}>
            <span>{l.product_id}</span>
            {l.hwid && <span>· HWID: {l.hwid.slice(0, 12)}…</span>}
            {l.customer && <span>· {l.customer}</span>}
          </div>
        </div>
      ))}

      {total > 20 && (
        <div className="flex-row" style={{ justifyContent: 'center' }}>
          <button className="sm secondary" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</button>
          <span style={{ fontSize: '0.85rem' }}>Page {page}</span>
          <button className="sm secondary" disabled={page * 20 >= total} onClick={() => setPage(p => p + 1)}>Next</button>
        </div>
      )}

      {showGen && (
        <div className="modal-overlay" onClick={() => setShowGen(false)}>
          <div className="modal-sheet" onClick={e => e.stopPropagation()}>
            <h3>Generate License</h3>
            <form onSubmit={generate}>
              <input placeholder="Product ID" value={genForm.product_id} onChange={e => setGenForm({ ...genForm, product_id: e.target.value })} required />
              <select value={genForm.duration} onChange={e => setGenForm({ ...genForm, duration: e.target.value })}>
                {['2_hours','1_day','3_days','1_week','1_month','2_months','6_months','1_year','lifetime'].map(d => <option key={d} value={d}>{d}</option>)}
              </select>
              <input placeholder="Features (comma-separated)" value={genForm.features} onChange={e => setGenForm({ ...genForm, features: e.target.value })} />
              <button type="submit">Generate</button>
            </form>
          </div>
        </div>
      )}

      <div className="nav">
        <Link to="/admin">🏠</Link>
        <Link to="/admin/licenses" className="active">🔑</Link>
        <Link to="/admin/products">📦</Link>
        <Link to="/admin/invites">✉️</Link>
      </div>
    </div>
  );
}
