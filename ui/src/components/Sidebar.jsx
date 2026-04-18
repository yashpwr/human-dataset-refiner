import { LayoutDashboard, Briefcase, Database, BarChart2, Activity, Sun, Moon } from 'lucide-react';

export default function Sidebar({ currentView, setCurrentView, theme, toggleTheme }) {
  const items = [
    { key: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { key: 'jobs',      icon: Briefcase,       label: 'Jobs' },
    { key: 'datasets',  icon: Database,        label: 'Datasets' },
    { key: 'report',    icon: BarChart2,       label: 'Pipeline Report' },
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
        {items.map(({ key, icon: Icon, label }) => (
          <div
            key={key}
            className={`nav-item ${currentView === key ? 'active' : ''}`}
            onClick={() => setCurrentView(key)}
          >
            <Icon size={18} /> {label}
          </div>
        ))}
      </div>
    </aside>
  );
}
