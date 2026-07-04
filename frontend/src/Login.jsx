import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState('admin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');

  if (user) {
    navigate(user.role === 'admin' ? '/admin' : '/reseller');
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await login(mode, { email, password, username });
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="page" style={{ paddingTop: '3rem', textAlign: 'center' }}>
      <h1 style={{ fontSize: '2rem', marginBottom: '0.25rem' }}>🔑 XyaPanel</h1>
      <p style={{ color: '#6b7280', marginBottom: '2rem' }}>Licensing Panel</p>

      <div className="flex-row" style={{ justifyContent: 'center', marginBottom: '1.5rem' }}>
        <button className={mode === 'admin' ? '' : 'secondary'} style={{ width: 'auto' }} onClick={() => setMode('admin')}>Admin</button>
        <button className={mode === 'reseller' ? '' : 'secondary'} style={{ width: 'auto' }} onClick={() => setMode('reseller')}>Reseller</button>
      </div>

      <form onSubmit={handleSubmit} style={{ textAlign: 'left' }}>
        {mode === 'admin' ? (
          <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required />
        ) : (
          <input type="text" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} required />
        )}
        <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} required />
        {error && <p style={{ color: '#dc2626', fontSize: '0.85rem', marginBottom: '0.5rem' }}>{error}</p>}
        <button type="submit">Sign In</button>
      </form>
    </div>
  );
}
