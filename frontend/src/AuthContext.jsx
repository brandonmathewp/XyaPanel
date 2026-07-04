import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import api from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('role');
    if (token && role) {
      setUser({ token, role });
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (type, credentials) => {
    let res;
    if (type === 'admin') {
      res = await api.adminLogin(credentials.email, credentials.password);
    } else {
      res = await api.resellerLogin(credentials.username, credentials.password);
    }
    localStorage.setItem('token', res.access_token);
    localStorage.setItem('role', res.role);
    setUser({ token: res.access_token, role: res.role });
    return res;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be inside AuthProvider');
  return ctx;
}
