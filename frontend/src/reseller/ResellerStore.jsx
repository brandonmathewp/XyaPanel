import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';

export default function ResellerStore() {
  const [products, setProducts] = useState([]);
  const [selected, setSelected] = useState(null);
  const [quantity, setQuantity] = useState(1);
  const [msg, setMsg] = useState('');

  const load = async () => {
    try {
      const data = await api.resellerStore();
      setProducts(data.data || []);
    } catch (e) { setMsg(e.message); }
  };

  useEffect(() => { load(); }, []);

  const purchase = async (productId, duration) => {
    try {
      await api.purchaseStock({ product_id: productId, duration, quantity });
      setMsg(`Purchased ${quantity}x ${duration}`);
      setSelected(null);
    } catch (e) { setMsg(e.message); }
  };

  return (
    <div className="page">
      <h2>Store</h2>
      {msg && <p style={{ color: '#16a34a', fontSize: '0.85rem' }}>{msg}</p>}

      {products.filter(p => p.store_enabled).map(p => (
        <div key={p.product_id} className="card">
          <strong>{p.name}</strong>
          <span className="pill" style={{ marginLeft: 6 }}>{p.product_id}</span>
          <div className="flex-row" style={{ flexWrap: 'wrap', marginTop: '0.5rem', gap: 4 }}>
            {(p.durations || []).filter(d => d.enabled !== false).map(d => (
              <button key={d.duration} className="sm" onClick={() => setSelected({ productId: p.product_id, duration: d.duration, price: d.price })}>
                {d.duration} — ${d.price}
              </button>
            ))}
          </div>
        </div>
      ))}

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal-sheet" onClick={e => e.stopPropagation()}>
            <h3>Purchase {selected.duration}</h3>
            <p style={{ color: '#6b7280' }}>${selected.price} each</p>
            <div className="flex-row" style={{ marginTop: '0.75rem' }}>
              <input type="number" min="1" max="100" value={quantity} onChange={e => setQuantity(Number(e.target.value))} style={{ width: '5rem', marginBottom: 0 }} />
              <span>× ${selected.price} = <strong>${(selected.price * quantity).toFixed(2)}</strong></span>
            </div>
            <button className="success" style={{ marginTop: '0.75rem' }} onClick={() => purchase(selected.productId, selected.duration)}>
              Purchase
            </button>
          </div>
        </div>
      )}

      <div className="nav">
        <Link to="/reseller">🏠</Link>
        <Link to="/reseller/store" className="active">🛒</Link>
        <Link to="/reseller/keys">🔑</Link>
        <Link to="/reseller/ledger">📒</Link>
      </div>
    </div>
  );
}
