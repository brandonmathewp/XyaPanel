import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';

export default function AdminInvites() {
  const [codes, setCodes] = useState([]);
  const [count, setCount] = useState(5);
  const [hours, setHours] = useState(72);
  const [msg, setMsg] = useState('');

  const load = async () => {
    try {
      const data = await api.listInviteCodes();
      setCodes(data.data || []);
    } catch (e) { setMsg(e.message); }
  };

  useEffect(() => { load(); }, []);

  const generate = async (e) => {
    e.preventDefault();
    try {
      await api.generateInviteCodes(count, hours);
      setMsg(`${count} code(s) generated`);
      load();
    } catch (e) { setMsg(e.message); }
  };

  return (
    <div className="page">
      <h2>Invite Codes</h2>

      <form onSubmit={generate} className="card flex-row" style={{ flexWrap: 'wrap' }}>
        <input type="number" min="1" max="50" value={count} onChange={e => setCount(Number(e.target.value))} style={{ width: '4rem', marginBottom: 0 }} />
        <span style={{ fontSize: '0.85rem' }}>codes for</span>
        <input type="number" min="1" max="168" value={hours} onChange={e => setHours(Number(e.target.value))} style={{ width: '4rem', marginBottom: 0 }} />
        <span style={{ fontSize: '0.85rem' }}>hours</span>
        <button className="sm" type="submit" style={{ marginBottom: 0 }}>Generate</button>
      </form>

      {msg && <p style={{ color: '#16a34a', fontSize: '0.85rem' }}>{msg}</p>}

      {codes.map(c => (
        <div key={c.code} className="card">
          <div style={{ fontFamily: 'monospace', fontSize: '0.85rem', wordBreak: 'break-all' }}>{c.code}</div>
          <div className="flex-row" style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.25rem' }}>
            <span>{c.is_used ? '✅ Used' : '🟢 Available'}</span>
            <span>· Expires: {new Date(c.expires_at).toLocaleDateString()}</span>
          </div>
        </div>
      ))}

      <div className="nav">
        <Link to="/admin">🏠</Link>
        <Link to="/admin/licenses">🔑</Link>
        <Link to="/admin/products">📦</Link>
        <Link to="/admin/invites" className="active">✉️</Link>
      </div>
    </div>
  );
}
