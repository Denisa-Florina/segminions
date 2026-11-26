import React from 'react';
import { NavLink } from 'react-router-dom';
import { Activity, BarChart3, Users, UserCog, LogOut } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import Avatar from '../common/Avatar';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: BarChart3 },
  // Not `end`: the item stays active on a patient's page (/patients/:id) too.
  { to: '/patients', label: 'Patients', icon: Users },
  { to: '/account', label: 'Account', icon: UserCog },
];

function navClass({ isActive }) {
  return `w-full flex items-center gap-3 px-4 py-3 rounded-lg transition font-medium ${
    isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-700 hover:text-white'
  }`;
}

function Sidebar() {
  const { doctor, logout } = useAuth();

  return (
    <aside className="w-64 shrink-0 bg-gray-800 border-r border-gray-700 flex flex-col">
      <div className="p-6 border-b border-gray-700">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
            <Activity className="w-6 h-6 text-white" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">MedSeg AI</h1>
            <p className="text-xs text-gray-400">Medical Imaging</p>
          </div>
        </div>
      </div>

      <nav aria-label="Main" className="flex-1 p-4 space-y-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={navClass}>
            <Icon className="w-5 h-5" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-700">
        <div className="flex items-center gap-3 mb-4">
          <Avatar name={doctor.name} size="sm" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white truncate">{doctor.name}</p>
            <p className="text-xs text-gray-400 truncate">{doctor.specialization}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={logout}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-700 hover:bg-red-600 text-white rounded-lg transition text-sm font-medium"
        >
          <LogOut className="w-4 h-4" aria-hidden="true" />
          Log out
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
