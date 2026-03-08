import { useState } from 'react';
import { useNavigate } from 'react-router';
import {
  ShieldCheck, Eye, EyeOff, Phone, Globe,
  ChevronRight, Lightbulb, Smartphone, Fingerprint, Headphones,
} from 'lucide-react';
import { HealthHubLogo } from '../components/HealthHubLogo';

const LANGUAGES = ['English', '中文', 'Melayu', 'தமிழ்'];

export function LoginPage() {
  const navigate = useNavigate();
  const [selectedLang, setSelectedLang] = useState('English');

  const handleSingpassLogin = () => {
    localStorage.setItem('hh_auth', '1');
    navigate('/app');
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: '#F4F7F5' }}>
      {/* Top bar */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <HealthHubLogo size="md" />
          <div className="flex items-center gap-1">
            {LANGUAGES.map((lang) => (
              <button
                key={lang}
                onClick={() => setSelectedLang(lang)}
                className="px-3 py-1.5 rounded-lg text-sm transition-colors"
                style={{
                  backgroundColor: selectedLang === lang ? '#1B6B45' : 'transparent',
                  color: selectedLang === lang ? 'white' : '#6B7280',
                }}
              >
                {lang}
              </button>
            ))}
          </div>
        </div>
        <div style={{ backgroundColor: '#1B6B45', height: '4px' }} />
      </header>

      {/* Main content */}
      <main className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-md">

          {/* Hero text */}
          <div className="text-center mb-8">
            <div
              className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg"
              style={{ background: 'linear-gradient(135deg, #1B9A7A 0%, #1B6B45 100%)' }}
            >
              <ShieldCheck size={36} className="text-white" />
            </div>
            <h1 className="text-3xl font-bold text-gray-800 mb-2">
              Your Health, Your Way
            </h1>
            <p className="text-gray-500 text-lg">
              Access all your health records, appointments, and services in one secure place.
            </p>
          </div>

          {/* Login Card */}
          <div className="bg-white rounded-2xl shadow-lg p-6 mb-4">
            <h2 className="text-xl font-semibold text-gray-800 mb-1">Sign in to HealthHub</h2>
            <p className="text-gray-500 text-sm mb-6">
              Use your Singpass credentials to securely access your health records.
            </p>

            {/* Singpass Button */}
            <button
              onClick={handleSingpassLogin}
              className="w-full flex items-center justify-center gap-3 py-4 rounded-xl text-white font-semibold text-lg shadow-md hover:shadow-lg active:scale-[0.98] transition-all mb-4"
              style={{ backgroundColor: '#E01B24' }}
            >
              {/* Singpass logo SVG simplified */}
              <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center flex-shrink-0">
                <span style={{ color: '#E01B24', fontWeight: 900, fontSize: '12px' }}>SP</span>
              </div>
              <span>Sign in with Singpass</span>
            </button>

            <div className="flex items-center gap-3 my-4">
              <div className="flex-1 border-t border-gray-200" />
              <span className="text-sm text-gray-400">or</span>
              <div className="flex-1 border-t border-gray-200" />
            </div>

            {/* App-based login */}
            <button
              onClick={handleSingpassLogin}
              className="w-full flex items-center justify-center gap-3 py-4 rounded-xl font-semibold text-base border-2 transition-all hover:bg-green-50"
              style={{ borderColor: '#1B6B45', color: '#1B6B45' }}
            >
              <Smartphone size={22} />
              <span>Use Singpass App QR Code</span>
            </button>

            <p className="text-center text-xs text-gray-400 mt-4">
              <ShieldCheck size={12} className="inline mr-1 text-green-600" />
              Your data is protected by government-grade encryption
            </p>
          </div>

          {/* Senior-Friendly Tips */}
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 mb-4">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-7 h-7 bg-amber-400 rounded-full flex items-center justify-center">
                <Lightbulb size={14} className="text-white" />
              </div>
              <h3 className="font-semibold text-amber-800">Senior-Friendly Tips</h3>
            </div>
            <ul className="space-y-2.5">
              {[
                { icon: Fingerprint, text: 'Use your fingerprint or Face ID on the Singpass app — no password needed!' },
                { icon: Smartphone, text: 'Ask a family member to help set up the Singpass app for easier access.' },
                { icon: Phone, text: 'Need help? Call our helpline: 1800-432-5843 (Mon–Fri, 8am–8pm).' },
                { icon: Globe, text: 'Available in 4 languages — change language using the buttons above.' },
              ].map(({ icon: Icon, text }, i) => (
                <li key={i} className="flex items-start gap-2.5 text-amber-800 text-sm">
                  <Icon size={16} className="mt-0.5 flex-shrink-0 text-amber-600" />
                  <span>{text}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Help options */}
          <div className="grid grid-cols-2 gap-3">
            <button className="bg-white rounded-xl p-4 flex items-center gap-2 shadow-sm hover:shadow-md transition-shadow border border-gray-100">
              <Phone size={20} style={{ color: '#1B6B45' }} />
              <div className="text-left">
                <p className="text-xs text-gray-500">Helpline</p>
                <p className="text-sm font-medium text-gray-800">1800-432-5843</p>
              </div>
            </button>
            <button className="bg-white rounded-xl p-4 flex items-center gap-2 shadow-sm hover:shadow-md transition-shadow border border-gray-100">
              <Headphones size={20} style={{ color: '#1B6B45' }} />
              <div className="text-left">
                <p className="text-xs text-gray-500">Live Chat</p>
                <p className="text-sm font-medium text-gray-800">Chat with Us</p>
              </div>
            </button>
          </div>

          {/* Register link */}
          <p className="text-center text-sm text-gray-500 mt-5">
            New to HealthHub?{' '}
            <button className="font-medium hover:underline" style={{ color: '#1B6B45' }}>
              Register with Singpass <ChevronRight size={14} className="inline" />
            </button>
          </p>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t py-4 px-4">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-center gap-4 text-xs text-gray-400">
          {['Privacy Statement', 'Terms of Use', 'Feedback', 'Rate Us', 'Sitemap'].map((link) => (
            <button key={link} className="hover:text-[#1B6B45] transition-colors">
              {link}
            </button>
          ))}
        </div>
        <p className="text-center text-xs text-gray-400 mt-2">
          © 2026 Ministry of Health, Singapore. Best viewed at 1024 × 768 resolution.
        </p>
      </footer>
    </div>
  );
}
