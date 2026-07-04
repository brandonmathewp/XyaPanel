import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import Login from './Login';
import AdminDashboard from './admin/AdminDashboard';
import AdminLicenses from './admin/AdminLicenses';
import AdminProducts from './admin/AdminProducts';
import AdminInvites from './admin/AdminInvites';
import ResellerDashboard from './reseller/ResellerDashboard';
import ResellerStore from './reseller/ResellerStore';
import ResellerKeys from './reseller/ResellerKeys';
import ResellerLedger from './reseller/ResellerLedger';

function ProtectedRoute({ children, role }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="page">Loading…</div>;
  if (!user) return <Navigate to="/" />;
  if (role && user.role !== role) return <Navigate to="/" />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/admin" element={<ProtectedRoute role="admin"><AdminDashboard /></ProtectedRoute>} />
      <Route path="/admin/licenses" element={<ProtectedRoute role="admin"><AdminLicenses /></ProtectedRoute>} />
      <Route path="/admin/products" element={<ProtectedRoute role="admin"><AdminProducts /></ProtectedRoute>} />
      <Route path="/admin/invites" element={<ProtectedRoute role="admin"><AdminInvites /></ProtectedRoute>} />
      <Route path="/reseller" element={<ProtectedRoute role="reseller"><ResellerDashboard /></ProtectedRoute>} />
      <Route path="/reseller/store" element={<ProtectedRoute role="reseller"><ResellerStore /></ProtectedRoute>} />
      <Route path="/reseller/keys" element={<ProtectedRoute role="reseller"><ResellerKeys /></ProtectedRoute>} />
      <Route path="/reseller/ledger" element={<ProtectedRoute role="reseller"><ResellerLedger /></ProtectedRoute>} />
    </Routes>
  );
}
