import { useState, useRef, useEffect } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router';
import {
  Search, Bell, User, Menu, X, Home, Calendar,
  FlaskConical, CreditCard, LogOut, Inbox,
  ShieldCheck, ChevronRight, Phone,
} from 'lucide-react';
import { HealthHubLogo } from './HealthHubLogo';

const ALL_SUGGESTIONS = [
  { label: 'Book Blood Test', category: 'Lab' },
  { label: 'Download Medical Certificate (MC)', category: 'Documents' },
  { label: 'View Lab Results', category: 'Lab' },
  { label: 'Make Appointment at SGH', category: 'Appointments' },
  { label: 'Make Appointment at NUH', category: 'Appointments' },
  { label: 'Check COVID-19 Vaccination', category: 'Immunisation' },
  { label: 'Pay Outstanding Bills', category: 'Payments' },
  { label: 'View Upcoming Appointments', category: 'Appointments' },
  { label: 'Download Vaccination Certificate', category: 'Immunisation' },
  { label: 'Check HbA1c Results', category: 'Lab' },
];

const NAV_LINKS = [
  'Highlights & Insights',
  'Health Conditions',
  'Medications & Treatments',
  'Well-being & Lifestyle',
  'Support & Tools',
];

const BOTTOM_NAV = [
  { icon: Home, label: 'Home', path: '/app' },
  { icon: Calendar, label: 'Appointments', path: '/app/appointments' },
  { icon: FlaskConical, label: 'Lab', path: '/app/lab-reports' },
  { icon: CreditCard, label: 'Payments', path: '/app/payments' },
  { icon: User, label: 'Profile', path: '/app/profile' },
];

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const [bannerVisible, setBannerVisible] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  const searchRef = useRef<HTMLDivElement>(null);

  const suggestions = ALL_SUGGESTIONS.filter(
    (s) =>
      searchQuery.length > 0 &&
      s.label.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleLogout = () => {
    localStorage.removeItem('hh_auth');
    navigate('/');
  };

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: '#F4F7F5' }}>
      {/* Announcement Banner */}
      {bannerVisible && (
        <div className="bg-gray-800 text-white text-sm py-2 px-4 flex items-center justify-between">
          <p className="flex-1 text-center">
            🔔 HealthHub eServices maintenance on 15 Mar 2026 from 10pm–6am. We apologise for any inconvenience.
          </p>
          <button
            onClick={() => setBannerVisible(false)}
            className="ml-4 text-gray-300 hover:text-white flex-shrink-0"
            aria-label="Close banner"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Top Header */}
      <header className="bg-white shadow-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center gap-3">
            {/* Logo */}
            <Link to="/app" className="flex-shrink-0">
              <HealthHubLogo size="md" />
            </Link>

            {/* Search */}
            <div className="flex-1 max-w-lg relative" ref={searchRef}>
              <div className="relative">
                <Search
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
                  size={18}
                />
                <input
                  type="text"
                  className="w-full pl-10 pr-4 py-2.5 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-[#1B6B45] bg-gray-50 text-base transition-colors"
                  placeholder="Search HealthHub..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  onBlur={() => setTimeout(() => setSearchFocused(false), 150)}
                />
              </div>
              {searchFocused && suggestions.length > 0 && (
                <div className="absolute top-full left-0 right-0 bg-white border border-gray-200 rounded-xl shadow-xl mt-1 z-50 overflow-hidden">
                  {suggestions.map((s, i) => (
                    <button
                      key={i}
                      className="w-full text-left px-4 py-3 hover:bg-green-50 flex items-center justify-between group border-b border-gray-100 last:border-0"
                      onMouseDown={(e) => e.preventDefault()}
                    >
                      <div className="flex items-center gap-3">
                        <Search size={15} className="text-[#1B6B45]" />
                        <span className="text-gray-800">{s.label}</span>
                      </div>
                      <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full group-hover:bg-green-100">
                        {s.category}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Right nav — desktop */}
            <div className="hidden md:flex items-center gap-1 ml-auto">
              <Link
                to="/app/profile"
                className="flex items-center gap-1.5 text-gray-600 hover:text-[#1B6B45] px-3 py-2 rounded-lg hover:bg-green-50 transition-colors text-sm"
              >
                <Inbox size={18} />
                <span>Inbox</span>
                <span className="bg-red-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">2</span>
              </Link>
              <Link
                to="/app/profile"
                className="flex items-center gap-1.5 text-gray-600 hover:text-[#1B6B45] px-3 py-2 rounded-lg hover:bg-green-50 transition-colors text-sm"
              >
                <User size={18} />
                <span>T**XX930C</span>
              </Link>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 text-gray-500 hover:text-red-600 px-3 py-2 rounded-lg hover:bg-red-50 transition-colors text-sm"
              >
                <LogOut size={18} />
                <span>Log out</span>
              </button>
            </div>

            {/* Hamburger — mobile */}
            <button
              className="md:hidden ml-auto p-2 rounded-lg hover:bg-gray-100"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Toggle menu"
            >
              {menuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          </div>

          {/* Secondary desktop links */}
          <div className="hidden md:flex items-center gap-6 mt-1 text-sm text-gray-500">
            <span>Also available in:</span>
            {['English', '中文', 'Melayu', 'தமிழ்'].map((lang, i) => (
              <button key={lang} className={`hover:text-[#1B6B45] ${i === 0 ? 'text-[#1B6B45] underline' : ''}`}>
                {lang}
              </button>
            ))}
          </div>
        </div>

        {/* Green Nav Bar */}
        <nav style={{ backgroundColor: '#1B6B45' }}>
          <div className="max-w-7xl mx-auto px-4">
            <div className="flex items-center overflow-x-auto scrollbar-hide">
              {NAV_LINKS.map((item) => (
                <button
                  key={item}
                  className="text-white text-sm py-3 px-4 hover:bg-black/20 whitespace-nowrap flex-shrink-0 transition-colors font-medium"
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        </nav>
      </header>

      {/* Mobile Slide Menu */}
      {menuOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="flex-1 bg-black/40" onClick={() => setMenuOpen(false)} />
          <div className="w-72 bg-white h-full overflow-y-auto shadow-2xl flex flex-col">
            <div className="p-4 flex items-center justify-between border-b" style={{ backgroundColor: '#1B6B45' }}>
              <HealthHubLogo size="sm" />
              <button onClick={() => setMenuOpen(false)} className="text-white">
                <X size={24} />
              </button>
            </div>
            <div className="p-4 bg-green-50 border-b">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-lg" style={{ backgroundColor: '#1B6B45' }}>
                  T
                </div>
                <div>
                  <p className="font-semibold text-gray-800">Tan Ah Kow</p>
                  <p className="text-sm text-gray-500">T**XX930C</p>
                </div>
              </div>
            </div>
            <div className="flex-1 p-2">
              {BOTTOM_NAV.map(({ icon: Icon, label, path }) => (
                <Link
                  key={path}
                  to={path}
                  className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-green-50 text-gray-700 hover:text-[#1B6B45] transition-colors"
                >
                  <Icon size={20} />
                  <span className="text-base">{label}</span>
                  <ChevronRight size={16} className="ml-auto text-gray-400" />
                </Link>
              ))}
            </div>
            <div className="p-4 border-t">
              <button
                onClick={() => { setMenuOpen(false); handleLogout(); }}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-red-600 hover:bg-red-50 transition-colors"
              >
                <LogOut size={20} />
                <span>Log out</span>
              </button>
              <div className="mt-3 p-3 bg-blue-50 rounded-lg">
                <div className="flex items-center gap-2 text-blue-700">
                  <Phone size={16} />
                  <span className="text-sm font-medium">Need help? Call 1800-432-5843</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 pb-20 md:pb-6">
        <Outlet />
      </main>

      {/* Mobile Bottom Nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-30 safe-area-bottom">
        <div className="flex">
          {BOTTOM_NAV.map(({ icon: Icon, label, path }) => {
            const active = location.pathname === path;
            return (
              <Link
                key={path}
                to={path}
                className="flex-1 flex flex-col items-center py-2.5 gap-0.5 transition-colors"
                style={{ color: active ? '#1B6B45' : '#9CA3AF' }}
              >
                <Icon size={22} strokeWidth={active ? 2.5 : 1.8} />
                <span className="text-xs font-medium">{label}</span>
                {active && (
                  <div className="w-5 h-0.5 rounded-full" style={{ backgroundColor: '#1B6B45' }} />
                )}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
