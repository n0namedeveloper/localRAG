import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';

const navItems = [
  { path: '/', label: 'Dashboard', icon: '◈' },
  { path: '/search', label: 'Search', icon: '⌕' },
  { path: '/chat', label: 'Chat', icon: '◎' },
  { path: '/logs', label: 'Logs', icon: '▤' },
];

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();

  // Don't wrap graph detail pages
  const isGraphPage = location.pathname.startsWith('/repos/');
  if (isGraphPage) return <>{children}</>;

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        width: 220,
        minWidth: 220,
        background: 'var(--bg-secondary)',
        borderRight: '1px solid var(--border-color)',
        display: 'flex',
        flexDirection: 'column',
        padding: '24px 0',
      }}>
        {/* Brand */}
        <div style={{ padding: '0 20px', marginBottom: 32 }}>
          <h1 style={{
            fontSize: 20,
            fontWeight: 800,
            letterSpacing: '-0.5px',
          }}>
            <span className="gradient-text">localRAG</span>
          </h1>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            Code Intelligence
          </p>
        </div>

        {/* Nav items */}
        <nav style={{ flex: 1 }}>
          {navItems.map(item => {
            const isActive = location.pathname === item.path;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 20px',
                  margin: '2px 8px',
                  borderRadius: 8,
                  textDecoration: 'none',
                  fontSize: 14,
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  background: isActive ? 'var(--bg-tertiary)' : 'transparent',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => {
                  if (!isActive) {
                    (e.target as HTMLElement).style.background = 'var(--bg-tertiary)';
                    (e.target as HTMLElement).style.color = 'var(--text-primary)';
                  }
                }}
                onMouseLeave={e => {
                  if (!isActive) {
                    (e.target as HTMLElement).style.background = 'transparent';
                    (e.target as HTMLElement).style.color = 'var(--text-secondary)';
                  }
                }}
              >
                <span style={{ fontSize: 16, width: 20, textAlign: 'center' }}>{item.icon}</span>
                {item.label}
                {isActive && (
                  <div style={{
                    marginLeft: 'auto',
                    width: 4,
                    height: 4,
                    borderRadius: '50%',
                    background: 'var(--accent-primary)',
                    boxShadow: '0 0 8px var(--accent-primary)',
                  }} />
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Footer */}
        <div style={{ padding: '0 20px', fontSize: 11, color: 'var(--text-muted)' }}>
          v0.1.0
        </div>
      </aside>

      {/* Main content */}
      <main style={{
        flex: 1,
        overflow: 'auto',
        background: 'var(--bg-primary)',
      }}>
        {children}
      </main>
    </div>
  );
};
