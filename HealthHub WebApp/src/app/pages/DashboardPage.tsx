import { useState } from 'react';
import { Link } from 'react-router';
import {
  Calendar, FlaskConical, CreditCard, ShieldCheck,
  Search, Bell, AlertCircle, ChevronRight,
  ArrowRight, Pill, Heart, Activity,
} from 'lucide-react';

const SUGGESTIONS = [
  'Book Blood Test',
  'Download Medical Certificate (MC)',
  'View Lab Results',
  'Make Appointment at SGH',
  'Check COVID-19 Vaccination',
  'Pay Outstanding Bills',
  'View Upcoming Appointments',
  'Download Vaccination Certificate',
];

const GRID_ITEMS = [
  {
    icon: Calendar,
    title: 'Appointments',
    description: '2 upcoming appointments',
    badge: '2',
    badgeColor: '#1B6B45',
    badgeBg: '#E8F5EE',
    buttonLabel: 'View Appointments',
    path: '/app/appointments',
    bgGradient: 'linear-gradient(135deg, #E8F5EE 0%, #D1EFE0 100%)',
    iconBg: '#1B6B45',
    detail: 'Next: SGH Cardiology — 15 Mar',
  },
  {
    icon: FlaskConical,
    title: 'Lab Reports',
    description: '3 results ready to view',
    badge: '3',
    badgeColor: '#1B6B45',
    badgeBg: '#E8F5EE',
    buttonLabel: 'View Reports',
    path: '/app/lab-reports',
    bgGradient: 'linear-gradient(135deg, #EEF2FF 0%, #DDE6FF 100%)',
    iconBg: '#4F46E5',
    detail: 'Latest: Full Blood Count — 2 Jan',
  },
  {
    icon: CreditCard,
    title: 'Payments',
    description: '$294.70 outstanding',
    badge: '3',
    badgeColor: '#B45309',
    badgeBg: '#FEF3C7',
    buttonLabel: 'View Bills',
    path: '/app/payments',
    bgGradient: 'linear-gradient(135deg, #FFF7ED 0%, #FFEDD5 100%)',
    iconBg: '#D97706',
    detail: '3 bills awaiting payment',
  },
  {
    icon: ShieldCheck,
    title: 'Immunisations',
    description: 'Up to date',
    badge: '✓',
    badgeColor: '#065F46',
    badgeBg: '#D1FAE5',
    buttonLabel: 'View Booklet',
    path: '/app/immunisations',
    bgGradient: 'linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%)',
    iconBg: '#16A34A',
    detail: 'COVID-19 & Flu vaccinations verified',
  },
];

const HEALTH_REMINDERS = [
  { icon: Pill, text: 'Take Metformin 500mg with dinner tonight', type: 'medication', color: '#7C3AED' },
  { icon: Activity, text: 'Your HbA1c result is pending — check back tomorrow', type: 'lab', color: '#1B6B45' },
  { icon: Heart, text: 'Annual cardiovascular screening due in April 2026', type: 'screening', color: '#DC2626' },
];

export function DashboardPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);

  const suggestions = SUGGESTIONS.filter(
    (s) => searchQuery.length > 0 && s.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* User Greeting */}
      <div className="flex items-start justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">
            Good morning, Tan Ah Kow! 👋
          </h1>
          <p className="text-gray-500 mt-0.5">
            View and manage your health records and transactions all in one place.
          </p>
        </div>
        <Link
          to="/app/profile"
          className="flex items-center gap-3 bg-white rounded-xl px-4 py-3 shadow-sm border border-gray-100 hover:shadow-md transition-shadow"
        >
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold"
            style={{ backgroundColor: '#1B6B45' }}
          >
            T
          </div>
          <div className="text-left">
            <p className="text-sm font-semibold text-gray-800">T**XX930C</p>
            <p className="text-xs text-[#1B6B45] flex items-center gap-0.5">
              Manage Profile <ChevronRight size={12} />
            </p>
          </div>
        </Link>
      </div>

      {/* Alert */}
      <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6">
        <AlertCircle size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-amber-800 font-medium">You have 3 outstanding bills totalling $294.70.</p>
          <p className="text-amber-700 text-sm mt-0.5">Please settle by 31 Mar 2026 to avoid late fees.</p>
        </div>
        <Link to="/app/payments" className="text-amber-700 text-sm font-medium hover:underline whitespace-nowrap">
          Pay now →
        </Link>
      </div>

      {/* Smart Search */}
      <div className="relative mb-8">
        <div className="flex items-center bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden">
          <Search size={22} className="ml-5 text-gray-400 flex-shrink-0" />
          <input
            type="text"
            className="flex-1 px-4 py-4 text-base text-gray-800 focus:outline-none bg-transparent placeholder-gray-400"
            placeholder="What do you need? Try 'Book Blood Test' or 'Download MC'..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setTimeout(() => setSearchFocused(false), 150)}
          />
          <button
            className="mr-3 px-5 py-2.5 rounded-xl text-white font-medium text-sm flex-shrink-0"
            style={{ backgroundColor: '#1B6B45' }}
          >
            Search
          </button>
        </div>

        {/* Suggestions dropdown */}
        {searchFocused && suggestions.length > 0 && (
          <div className="absolute top-full left-0 right-0 bg-white border border-gray-200 rounded-2xl shadow-xl mt-2 z-20 overflow-hidden">
            <p className="px-4 py-2 text-xs text-gray-400 uppercase tracking-wide border-b">Suggestions</p>
            {suggestions.map((s, i) => (
              <button
                key={i}
                className="w-full text-left px-4 py-3.5 hover:bg-green-50 flex items-center gap-3 border-b border-gray-50 last:border-0 group"
                onMouseDown={(e) => { e.preventDefault(); setSearchQuery(s); setSearchFocused(false); }}
              >
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-[#1B6B45] bg-gray-100 transition-colors">
                  <Search size={14} className="text-gray-500 group-hover:text-white" />
                </div>
                <span className="text-gray-700">{s}</span>
                <ArrowRight size={14} className="ml-auto text-gray-300 group-hover:text-[#1B6B45]" />
              </button>
            ))}
          </div>
        )}

        {/* Quick suggestions when not typing */}
        {searchFocused && searchQuery.length === 0 && (
          <div className="absolute top-full left-0 right-0 bg-white border border-gray-200 rounded-2xl shadow-xl mt-2 z-20 overflow-hidden">
            <p className="px-4 py-2 text-xs text-gray-400 uppercase tracking-wide border-b">Popular searches</p>
            {SUGGESTIONS.slice(0, 5).map((s, i) => (
              <button
                key={i}
                className="w-full text-left px-4 py-3.5 hover:bg-green-50 flex items-center gap-3 border-b border-gray-50 last:border-0 group"
                onMouseDown={(e) => { e.preventDefault(); setSearchQuery(s); }}
              >
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-gray-100 group-hover:bg-[#1B6B45] transition-colors">
                  <Search size={14} className="text-gray-500 group-hover:text-white" />
                </div>
                <span className="text-gray-700">{s}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 4-Grid Navigation */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
        {GRID_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.title}
              to={item.path}
              className="group bg-white rounded-2xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-all hover:-translate-y-0.5 block"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: item.iconBg }}
                  >
                    <Icon size={24} className="text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-800 text-base">{item.title}</h3>
                    <p className="text-sm text-gray-500">{item.description}</p>
                  </div>
                </div>
                <span
                  className="text-xs font-bold px-2 py-0.5 rounded-full"
                  style={{ color: item.badgeColor, backgroundColor: item.badgeBg }}
                >
                  {item.badge}
                </span>
              </div>

              <div className="text-xs text-gray-400 mb-4 pl-1">{item.detail}</div>

              <button
                className="w-full py-3 rounded-xl text-white font-medium text-sm flex items-center justify-center gap-2 group-hover:opacity-90 transition-opacity"
                style={{ backgroundColor: '#1B6B45' }}
              >
                {item.buttonLabel}
                <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
              </button>
            </Link>
          );
        })}
      </div>

      {/* Health Reminders */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-gray-800 text-lg flex items-center gap-2">
            <Bell size={18} style={{ color: '#1B6B45' }} />
            Health Reminders
          </h2>
          <button className="text-sm text-[#1B6B45] hover:underline">View all</button>
        </div>
        <div className="space-y-3">
          {HEALTH_REMINDERS.map((reminder, i) => {
            const Icon = reminder.icon;
            return (
              <div
                key={i}
                className="bg-white rounded-xl p-4 flex items-center gap-3 shadow-sm border border-gray-100"
              >
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: `${reminder.color}15` }}
                >
                  <Icon size={18} style={{ color: reminder.color }} />
                </div>
                <p className="text-sm text-gray-700 flex-1">{reminder.text}</p>
                <ChevronRight size={16} className="text-gray-300 flex-shrink-0" />
              </div>
            );
          })}
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="font-semibold text-gray-800 text-lg mb-3">Quick Actions</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'New Appointment', icon: Calendar, path: '/app/appointments' },
            { label: 'Download MC', icon: FlaskConical, path: '/app/lab-reports' },
            { label: 'Pay Bills', icon: CreditCard, path: '/app/payments' },
            { label: 'View Vaccinations', icon: ShieldCheck, path: '/app/immunisations' },
          ].map(({ label, icon: Icon, path }) => (
            <Link
              key={label}
              to={path}
              className="bg-white rounded-xl p-4 flex flex-col items-center gap-2 shadow-sm border border-gray-100 hover:shadow-md hover:border-[#1B6B45]/30 transition-all text-center group"
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center transition-colors"
                style={{ backgroundColor: '#E8F5EE' }}
              >
                <Icon size={20} style={{ color: '#1B6B45' }} />
              </div>
              <span className="text-sm text-gray-700 font-medium">{label}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
