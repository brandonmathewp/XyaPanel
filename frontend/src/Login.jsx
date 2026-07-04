import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import api from './api';

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState('admin');
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');

  if (user) {
    navigate(user.role === 'admin' ? '/admin' : '/reseller');
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMsg('');

    if (mode === 'reseller' && isRegister) {
      try {
        const res = await api.resellerRegister({ username, email, password, invite_code: inviteCode });
        localStorage.setItem('token', res.access_token);
        localStorage.setItem('role', res.role);
        setMsg('Registered! Redirecting…');
        setTimeout(() => navigate('/reseller'), 500);
      } catch (err) {
        setError(err.message);
      }
      return;
    }

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
        <button className={mode === 'admin' ? '' : 'secondary'} style={{ width: 'auto' }} onClick={() => { setMode('admin'); setIsRegister(false); }}>Admin</button>
        <button className={mode === 'reseller' ? '' : 'secondary'} style={{ width: 'auto' }} onClick={() => setMode('reseller')}>Reseller</button>
      </div>

      {mode === 'reseller' && (
        <div className="flex-row" style={{ justifyContent: 'center', marginBottom: '1rem' }}>
          <button className={!isRegister ? 'sm' : 'sm secondary'} style={{ width: 'auto' }} onClick={() => setIsRegister(false)}>Sign In</button>
          <button className={isRegister ? 'sm' : 'sm secondary'} style={{ width: 'auto' }} onClick={() => setIsRegister(true)}>Register</button>
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ textAlign: 'left' }}>
        {mode === 'admin' ? (
          <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required />
        ) : isRegister ? (
          <>
            <input type="text" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} required />
            <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required />
            <input type="text" placeholder="Invite Code" value={inviteCode} onChange={e => setInviteCode(e.target.value)} required />
          </>
        ) : (
          <input type="text" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} required />
        )}
        <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} required />
        {error && <p style={{ color: '#dc2626', fontSize: '0.85rem', marginBottom: '0.5rem' }}>{error}</p>}
        {msg && <p style={{ color: '#16a34a', fontSize: '0.85rem', marginBottom: '0.5rem' }}>{msg}</p>}
        <button type="submit">{isRegister ? 'Register' : 'Sign In'}</button>
      </form>
    </div>
  );
}
