import { useState } from 'react';
import { Link } from 'react-router';
import {
  ShieldCheck, ChevronLeft, Download, CheckCircle,
  AlertTriangle, Clock, QrCode, Share2, ChevronDown,
  Info, Calendar, Building2, FileText,
} from 'lucide-react';

interface Vaccine {
  id: string;
  name: string;
  shortName: string;
  category: string;
  doses: { dose: number; date: string; batch: string; administered: string }[];
  status: 'verified' | 'due_soon' | 'overdue' | 'not_required';
  nextDue?: string;
  interval: string;
  description: string;
  icon: string;
}

const VACCINES: Vaccine[] = [
  {
    id: '1',
    name: 'COVID-19 mRNA Vaccine (Moderna)',
    shortName: 'COVID-19',
    category: 'Infectious Disease',
    doses: [
      { dose: 1, date: '20 Mar 2021', batch: 'MOD-B1231', administered: 'Clementi CC Vaccination Centre' },
      { dose: 2, date: '17 Apr 2021', batch: 'MOD-C4521', administered: 'Clementi CC Vaccination Centre' },
      { dose: 3, date: '15 Oct 2023', batch: 'MOD-XBB012', administered: 'NHGP Health Hub' },
    ],
    status: 'verified',
    interval: 'As recommended by MOH',
    description: 'mRNA COVID-19 vaccine (Spikevax) — XBB.1.5 formulation',
    icon: '🦠',
  },
  {
    id: '2',
    name: 'Influenza Vaccine (Inactivated)',
    shortName: 'Influenza (Flu)',
    category: 'Seasonal',
    doses: [
      { dose: 1, date: '10 Dec 2025', batch: 'FLU-2025-088', administered: 'Clementi Polyclinic' },
    ],
    status: 'verified',
    nextDue: 'Dec 2026',
    interval: 'Annual (yearly)',
    description: 'Quadrivalent inactivated influenza vaccine — 2025/2026 season formulation',
    icon: '💉',
  },
  {
    id: '3',
    name: 'Tetanus, Diphtheria & Pertussis (Tdap)',
    shortName: 'Tdap',
    category: 'Routine',
    doses: [
      { dose: 1, date: '3 Mar 2021', batch: 'TDAP-21-445', administered: 'SGH Specialist Clinic' },
    ],
    status: 'verified',
    nextDue: 'Mar 2031',
    interval: 'Every 10 years',
    description: 'Combined Tdap booster for tetanus, diphtheria, and whooping cough.',
    icon: '🩺',
  },
  {
    id: '4',
    name: 'Hepatitis B Vaccine',
    shortName: 'Hepatitis B',
    category: 'Routine',
    doses: [
      { dose: 1, date: '5 Jan 2018', batch: 'HEPB-1801', administered: 'NUH Medical Centre' },
      { dose: 2, date: '5 Feb 2018', batch: 'HEPB-1802', administered: 'NUH Medical Centre' },
      { dose: 3, date: '5 Jul 2018', batch: 'HEPB-1803', administered: 'NUH Medical Centre' },
    ],
    status: 'verified',
    interval: 'Lifetime (3-dose series)',
    description: 'Full 3-dose Hepatitis B immunisation series completed. No booster required.',
    icon: '🏥',
  },
  {
    id: '5',
    name: 'Pneumococcal Vaccine (PCV13)',
    shortName: 'Pneumococcal',
    category: 'Seniors',
    doses: [
      { dose: 1, date: '5 Jul 2024', batch: 'PCV-2024-331', administered: 'Clementi Polyclinic' },
    ],
    status: 'verified',
    interval: 'One-time (PCV13) + PPSV23 in 1 year',
    description: 'Protects against pneumonia — especially important for adults over 65.',
    icon: '🫁',
  },
  {
    id: '6',
    name: 'Herpes Zoster / Shingles (Zostavax)',
    shortName: 'Shingles',
    category: 'Seniors',
    doses: [],
    status: 'due_soon',
    nextDue: 'Apr 2026',
    interval: 'One-time (age 60+)',
    description: 'Recommended for adults aged 60 and above to prevent shingles.',
    icon: '⚠️',
  },
];

const STATUS_CONFIG = {
  verified: {
    label: 'Verified',
    icon: CheckCircle,
    color: '#065F46',
    bg: '#D1FAE5',
    border: '#6EE7B7',
    textColor: '#065F46',
  },
  due_soon: {
    label: 'Due Soon',
    icon: AlertTriangle,
    color: '#92400E',
    bg: '#FEF3C7',
    border: '#FCD34D',
    textColor: '#92400E',
  },
  overdue: {
    label: 'Overdue',
    icon: AlertTriangle,
    color: '#991B1B',
    bg: '#FEE2E2',
    border: '#FCA5A5',
    textColor: '#991B1B',
  },
  not_required: {
    label: 'Not Required',
    icon: CheckCircle,
    color: '#6B7280',
    bg: '#F3F4F6',
    border: '#D1D5DB',
    textColor: '#6B7280',
  },
};

export function ImmunisationsPage() {
  const [expandedId, setExpandedId] = useState<string | null>('1');
  const [showQr, setShowQr] = useState(false);

  const verifiedCount = VACCINES.filter((v) => v.status === 'verified').length;
  const dueSoonCount = VACCINES.filter((v) => v.status === 'due_soon').length;

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <Link
          to="/app"
          className="w-10 h-10 rounded-xl flex items-center justify-center hover:bg-gray-200 bg-white shadow-sm border border-gray-100"
        >
          <ChevronLeft size={20} className="text-gray-600" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-800">Health Booklet</h1>
          <p className="text-gray-500 text-sm">Your digital immunisation records</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowQr(!showQr)}
            className="w-10 h-10 rounded-xl flex items-center justify-center bg-white shadow-sm border border-gray-100 hover:bg-gray-50"
          >
            <QrCode size={18} className="text-gray-600" />
          </button>
          <button className="w-10 h-10 rounded-xl flex items-center justify-center bg-white shadow-sm border border-gray-100 hover:bg-gray-50">
            <Share2 size={18} className="text-gray-600" />
          </button>
        </div>
      </div>

      {/* Official Booklet Header */}
      <div
        className="rounded-2xl p-5 mb-5 text-white relative overflow-hidden"
        style={{ background: 'linear-gradient(135deg, #1B6B45 0%, #0F4229 100%)' }}
      >
        <div className="absolute top-0 right-0 w-32 h-32 rounded-full bg-white/5 -translate-y-8 translate-x-8" />
        <div className="absolute bottom-0 left-0 w-24 h-24 rounded-full bg-white/5 translate-y-8 -translate-x-8" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <ShieldCheck size={22} />
            <span className="text-sm font-medium opacity-90">Official Health Record</span>
          </div>
          <h2 className="text-xl font-bold mb-0.5">Tan Ah Kow</h2>
          <p className="opacity-80 text-sm mb-4">NRIC: T**XX930C · DOB: 15 Mar 1952</p>

          <div className="grid grid-cols-3 gap-3">
            <div className="bg-white/20 rounded-xl p-3 text-center backdrop-blur-sm">
              <p className="text-2xl font-bold">{verifiedCount}</p>
              <p className="text-xs opacity-80 mt-0.5">Verified</p>
            </div>
            <div className="bg-white/20 rounded-xl p-3 text-center backdrop-blur-sm">
              <p className="text-2xl font-bold">{dueSoonCount}</p>
              <p className="text-xs opacity-80 mt-0.5">Due Soon</p>
            </div>
            <div className="bg-white/20 rounded-xl p-3 text-center backdrop-blur-sm">
              <p className="text-2xl font-bold">{VACCINES.length}</p>
              <p className="text-xs opacity-80 mt-0.5">Total</p>
            </div>
          </div>
        </div>
      </div>

      {/* QR Code section */}
      {showQr && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 mb-5 text-center">
          <p className="font-semibold text-gray-700 mb-3">Verification QR Code</p>
          <div className="w-40 h-40 bg-gray-100 rounded-xl mx-auto flex items-center justify-center mb-3 border-2 border-dashed border-gray-300">
            <div className="grid grid-cols-5 gap-1 p-2">
              {Array.from({ length: 25 }).map((_, i) => (
                <div
                  key={i}
                  className="w-5 h-5 rounded-sm"
                  style={{ backgroundColor: Math.random() > 0.5 ? '#1B6B45' : 'transparent' }}
                />
              ))}
            </div>
          </div>
          <p className="text-xs text-gray-500">Scan to verify immunisation records</p>
          <p className="text-xs text-gray-400 mt-1">Valid for 15 minutes · Powered by Singpass</p>
        </div>
      )}

      {/* Due Soon Alert */}
      {dueSoonCount > 0 && (
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4 mb-5">
          <AlertTriangle size={18} className="text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-amber-800 font-medium text-sm">1 vaccination due soon</p>
            <p className="text-amber-700 text-xs mt-0.5">
              Shingles (Zostavax) is due in Apr 2026. Book your appointment at any polyclinic.
            </p>
          </div>
          <button className="text-amber-700 text-xs font-medium underline whitespace-nowrap">Book now</button>
        </div>
      )}

      {/* Vaccine Cards */}
      <div className="space-y-3 mb-6">
        {VACCINES.map((vaccine) => {
          const statusCfg = STATUS_CONFIG[vaccine.status];
          const StatusIcon = statusCfg.icon;
          const isExpanded = expandedId === vaccine.id;

          return (
            <div
              key={vaccine.id}
              className="bg-white rounded-2xl shadow-sm border overflow-hidden"
              style={{ borderColor: isExpanded ? statusCfg.border : '#E5E7EB' }}
            >
              <button
                className="w-full text-left p-5"
                onClick={() => setExpandedId(isExpanded ? null : vaccine.id)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div
                      className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl flex-shrink-0"
                      style={{ backgroundColor: statusCfg.bg }}
                    >
                      {vaccine.icon}
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-800">{vaccine.shortName}</h3>
                      <p className="text-xs text-gray-500 mt-0.5">{vaccine.name}</p>
                      <div className="flex items-center gap-1.5 mt-2">
                        <span
                          className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-0.5 rounded-full border"
                          style={{
                            color: statusCfg.textColor,
                            backgroundColor: statusCfg.bg,
                            borderColor: statusCfg.border,
                          }}
                        >
                          <StatusIcon size={10} />
                          {statusCfg.label}
                        </span>
                        <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                          {vaccine.category}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div className="flex items-center gap-1 text-xs text-gray-500 bg-gray-50 px-2 py-1 rounded-lg">
                      <span>{vaccine.doses.length} dose{vaccine.doses.length !== 1 ? 's' : ''}</span>
                    </div>
                    <ChevronDown
                      size={16}
                      className="text-gray-400 transition-transform"
                      style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
                    />
                  </div>
                </div>
              </button>

              {isExpanded && (
                <div className="border-t border-gray-100">
                  <div className="px-5 py-4">
                    <div className="flex items-start gap-2 mb-4 text-sm text-gray-600 bg-blue-50 rounded-xl p-3">
                      <Info size={14} className="flex-shrink-0 mt-0.5 text-blue-600" />
                      <p>{vaccine.description}</p>
                    </div>

                    {/* Interval */}
                    <div className="flex items-center gap-2 text-sm text-gray-600 mb-4">
                      <Calendar size={14} style={{ color: '#1B6B45' }} />
                      <span>Interval: <strong>{vaccine.interval}</strong></span>
                    </div>

                    {/* Dose history */}
                    {vaccine.doses.length > 0 ? (
                      <div className="mb-4">
                        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                          Dose History
                        </h4>
                        <div className="space-y-2">
                          {vaccine.doses.map((dose) => (
                            <div
                              key={dose.dose}
                              className="flex items-start gap-3 bg-gray-50 rounded-xl p-3"
                            >
                              <div
                                className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                                style={{ backgroundColor: '#1B6B45' }}
                              >
                                {dose.dose}
                              </div>
                              <div className="flex-1">
                                <div className="flex items-center justify-between">
                                  <p className="text-sm font-medium text-gray-700">Dose {dose.dose}</p>
                                  <p className="text-xs text-gray-500">{dose.date}</p>
                                </div>
                                <div className="flex items-center gap-1.5 mt-0.5">
                                  <Building2 size={11} className="text-gray-400" />
                                  <p className="text-xs text-gray-500">{dose.administered}</p>
                                </div>
                                <p className="text-xs text-gray-400 mt-0.5">Batch: {dose.batch}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="bg-amber-50 border border-amber-100 rounded-xl p-4 mb-4 text-center">
                        <Clock size={24} className="mx-auto text-amber-500 mb-2" />
                        <p className="text-sm font-medium text-amber-800">Not yet vaccinated</p>
                        <p className="text-xs text-amber-700 mt-1">
                          Due: {vaccine.nextDue} — book at any polyclinic or GP
                        </p>
                      </div>
                    )}

                    {vaccine.nextDue && vaccine.doses.length > 0 && (
                      <div className="flex items-center gap-2 text-sm mb-4">
                        <Clock size={14} style={{ color: '#1B6B45' }} />
                        <span className="text-gray-600">
                          Next dose due: <strong style={{ color: '#1B6B45' }}>{vaccine.nextDue}</strong>
                        </span>
                      </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex gap-2">
                      <button
                        className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-white text-sm font-medium"
                        style={{ backgroundColor: '#1B6B45' }}
                      >
                        <Download size={15} />
                        Download Certificate
                      </button>
                      <button className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 text-gray-600 hover:bg-gray-50 text-sm">
                        <FileText size={15} />
                        Details
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Download full booklet */}
      <div
        className="rounded-2xl p-5 flex items-center justify-between"
        style={{ background: 'linear-gradient(135deg, #E8F5EE 0%, #D1FAE5 100%)' }}
      >
        <div>
          <h3 className="font-semibold text-gray-800">Download Full Immunisation Booklet</h3>
          <p className="text-sm text-gray-600 mt-0.5">Official digital copy accepted at borders and clinics</p>
        </div>
        <button
          className="flex items-center gap-2 px-4 py-3 rounded-xl text-white font-medium text-sm flex-shrink-0 ml-4"
          style={{ backgroundColor: '#1B6B45' }}
        >
          <Download size={16} />
          PDF
        </button>
      </div>
    </div>
  );
}
