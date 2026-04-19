import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Briefcase, Database, BarChart2, Activity, Sun, Moon } from 'lucide-react';

export default function Sidebar({ theme, toggleTheme }) {
  const items = [
    { to: '/',          icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/jobs',      icon: Briefcase,       label: 'Jobs' },
    { to: '/datasets',  icon: Database,        label: 'Datasets' },
    { to: '/report',    icon: BarChart2,       label: 'Pipeline Report' },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand">
          <Activity size={20} color="var(--primary-color)" />
          Dataset Refiner
        </div>
        <button className="theme-toggle-btn" onClick={toggleTheme}>
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
      <div className="nav-links">
        {items.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon size={18} /> {label}
          </NavLink>
        ))}
      </div>
    </aside>
  );
}
