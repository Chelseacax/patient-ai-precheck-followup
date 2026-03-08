import { useState } from 'react';
import { Link } from 'react-router';
import {
  FlaskConical, Download, ChevronLeft, Search,
  CheckCircle, Clock, AlertTriangle, FileText,
  RefreshCw, Info,
} from 'lucide-react';

interface LabReport {
  id: string;
  testName: string;
  date: string;
  hospital: string;
  doctor: string;
  status: 'ready' | 'pending' | 'abnormal';
  category: string;
  resultSummary?: string;
  referenceRange?: string;
  value?: string;
  unit?: string;
}

const REPORTS: LabReport[] = [
  {
    id: '1',
    testName: 'Full Blood Count (FBC)',
    date: '2 Jan 2026',
    hospital: 'Singapore General Hospital',
    doctor: 'Dr. Lee Cheng Hwa',
    status: 'ready',
    category: 'Haematology',
    resultSummary: 'Within normal limits',
    value: 'Normal',
    referenceRange: 'See full report',
  },
  {
    id: '2',
    testName: 'HbA1c (Glycated Haemoglobin)',
    date: '10 Feb 2026',
    hospital: 'Clementi Polyclinic',
    doctor: 'Dr. Rajesh Kumar',
    status: 'pending',
    category: 'Biochemistry',
    resultSummary: 'Awaiting laboratory processing',
  },
  {
    id: '3',
    testName: 'Lipid Panel (Cholesterol)',
    date: '28 Dec 2025',
    hospital: 'National University Hospital',
    doctor: 'Dr. Wong Mei Lin',
    status: 'abnormal',
    category: 'Biochemistry',
    resultSummary: 'LDL slightly elevated — consult doctor',
    value: '3.8 mmol/L',
    unit: 'mmol/L',
    referenceRange: '< 3.4 mmol/L',
  },
  {
    id: '4',
    testName: 'Kidney Function Test (KFT)',
    date: '2 Jan 2026',
    hospital: 'Singapore General Hospital',
    doctor: 'Dr. Lee Cheng Hwa',
    status: 'ready',
    category: 'Biochemistry',
    resultSummary: 'Within normal limits',
    value: 'Normal',
    referenceRange: 'See full report',
  },
  {
    id: '5',
    testName: 'Urine FEME',
    date: '5 Feb 2026',
    hospital: 'Clementi Polyclinic',
    doctor: 'Dr. Rajesh Kumar',
    status: 'pending',
    category: 'Urinalysis',
    resultSummary: 'Awaiting laboratory processing',
  },
  {
    id: '6',
    testName: 'Liver Function Test (LFT)',
    date: '15 Jan 2026',
    hospital: 'Tan Tock Seng Hospital',
    doctor: 'Dr. Ahmad Farid',
    status: 'ready',
    category: 'Biochemistry',
    resultSummary: 'Within normal limits',
    value: 'Normal',
    referenceRange: 'See full report',
  },
];

type FilterTab = 'all' | 'ready' | 'pending' | 'abnormal';

const STATUS_CONFIG = {
  ready: {
    label: 'Result Ready',
    icon: CheckCircle,
    color: '#065F46',
    bg: '#D1FAE5',
    border: '#6EE7B7',
  },
  pending: {
    label: 'Pending',
    icon: Clock,
    color: '#92400E',
    bg: '#FEF3C7',
    border: '#FCD34D',
  },
  abnormal: {
    label: 'Attention Required',
    icon: AlertTriangle,
    color: '#991B1B',
    bg: '#FEE2E2',
    border: '#FCA5A5',
  },
};

export function LabReportsPage() {
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = REPORTS.filter((r) => {
    const matchFilter = activeFilter === 'all' || r.status === activeFilter;
    const matchSearch =
      searchQuery === '' ||
      r.testName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.hospital.toLowerCase().includes(searchQuery.toLowerCase());
    return matchFilter && matchSearch;
  });

  const counts = {
    all: REPORTS.length,
    ready: REPORTS.filter((r) => r.status === 'ready').length,
    pending: REPORTS.filter((r) => r.status === 'pending').length,
    abnormal: REPORTS.filter((r) => r.status === 'abnormal').length,
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      {/* Page Header */}
      <div className="flex items-center gap-3 mb-5">
        <Link
          to="/app"
          className="w-10 h-10 rounded-xl flex items-center justify-center hover:bg-gray-200 transition-colors bg-white shadow-sm border border-gray-100"
        >
          <ChevronLeft size={20} className="text-gray-600" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Lab Reports</h1>
          <p className="text-gray-500 text-sm">View and download your general lab test results.</p>
        </div>
        <button className="ml-auto w-10 h-10 rounded-xl flex items-center justify-center bg-white shadow-sm border border-gray-100 hover:bg-gray-50">
          <RefreshCw size={18} className="text-gray-500" />
        </button>
      </div>

      {/* Info Banner */}
      <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl p-4 mb-5">
        <Info size={18} className="text-blue-600 flex-shrink-0 mt-0.5" />
        <p className="text-blue-800 text-sm">
          Lab results are typically available within <strong>1–3 working days</strong> after your test. 
          Always consult your doctor to interpret results.
        </p>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
        <input
          type="text"
          className="w-full pl-10 pr-4 py-3 bg-white border border-gray-200 rounded-xl focus:outline-none focus:border-[#1B6B45] focus:ring-2 focus:ring-[#1B6B45]/20 text-base"
          placeholder="Search by test name or hospital..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-5 overflow-x-auto pb-1">
        {(['all', 'ready', 'pending', 'abnormal'] as FilterTab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveFilter(tab)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-all border"
            style={
              activeFilter === tab
                ? { backgroundColor: '#1B6B45', color: 'white', borderColor: '#1B6B45' }
                : { backgroundColor: 'white', color: '#4B5563', borderColor: '#E5E7EB' }
            }
          >
            <span className="capitalize">{tab === 'all' ? 'All Reports' : tab === 'abnormal' ? 'Attention' : tab === 'ready' ? 'Ready' : 'Pending'}</span>
            <span
              className="text-xs px-1.5 py-0.5 rounded-full"
              style={
                activeFilter === tab
                  ? { backgroundColor: 'rgba(255,255,255,0.3)', color: 'white' }
                  : { backgroundColor: '#F3F4F6', color: '#6B7280' }
              }
            >
              {counts[tab]}
            </span>
          </button>
        ))}
      </div>

      {/* Reports List */}
      <div className="space-y-3">
        {filtered.map((report) => {
          const statusCfg = STATUS_CONFIG[report.status];
          const StatusIcon = statusCfg.icon;
          const isExpanded = expandedId === report.id;

          return (
            <div
              key={report.id}
              className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden"
            >
              <button
                className="w-full text-left p-5"
                onClick={() => setExpandedId(isExpanded ? null : report.id)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 flex-1">
                    <div
                      className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: '#E8F5EE' }}
                    >
                      <FlaskConical size={22} style={{ color: '#1B6B45' }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-gray-800 text-base">{report.testName}</h3>
                      <p className="text-sm text-gray-500 mt-0.5">{report.hospital}</p>
                      <p className="text-xs text-gray-400 mt-0.5">{report.date} · {report.doctor}</p>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2 flex-shrink-0">
                    <span
                      className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border"
                      style={{
                        color: statusCfg.color,
                        backgroundColor: statusCfg.bg,
                        borderColor: statusCfg.border,
                      }}
                    >
                      <StatusIcon size={11} />
                      {statusCfg.label}
                    </span>
                    <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                      {report.category}
                    </span>
                  </div>
                </div>

                {/* Summary */}
                <div
                  className="mt-3 ml-14 text-sm rounded-lg px-3 py-2"
                  style={{ backgroundColor: statusCfg.bg, color: statusCfg.color }}
                >
                  {report.resultSummary}
                </div>
              </button>

              {/* Expanded details */}
              {isExpanded && report.status !== 'pending' && (
                <div className="border-t border-gray-100 px-5 pb-5 pt-4">
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    {report.value && (
                      <div className="bg-gray-50 rounded-xl p-3">
                        <p className="text-xs text-gray-500 mb-1">Your Result</p>
                        <p className="text-base font-bold text-gray-800">{report.value}</p>
                      </div>
                    )}
                    {report.referenceRange && (
                      <div className="bg-gray-50 rounded-xl p-3">
                        <p className="text-xs text-gray-500 mb-1">Reference Range</p>
                        <p className="text-base font-bold text-gray-800">{report.referenceRange}</p>
                      </div>
                    )}
                  </div>
                  <div className="flex gap-3">
                    <button
                      className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-white font-medium text-sm"
                      style={{ backgroundColor: '#1B6B45' }}
                    >
                      <Download size={16} />
                      Download PDF Report
                    </button>
                    <button className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-gray-200 text-gray-600 hover:bg-gray-50 text-sm">
                      <FileText size={16} />
                      Details
                    </button>
                  </div>
                </div>
              )}

              {/* Pending footer */}
              {report.status === 'pending' && (
                <div className="border-t border-gray-100 px-5 py-3 bg-amber-50 flex items-center gap-2">
                  <Clock size={14} className="text-amber-600" />
                  <p className="text-sm text-amber-700">
                    Results expected within 1–3 working days. We'll notify you when ready.
                  </p>
                </div>
              )}
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div className="text-center py-12 bg-white rounded-2xl border border-gray-100">
            <FlaskConical size={40} className="mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500">No reports found matching your search.</p>
          </div>
        )}
      </div>

      {/* Disclaimer */}
      <div className="mt-6 p-4 bg-gray-50 rounded-xl border border-gray-200">
        <p className="text-xs text-gray-500 text-center">
          <strong>Disclaimer:</strong> Lab results shown are for reference only. 
          Please consult your healthcare provider for medical advice. Results may take up to 3 working days to appear.
        </p>
      </div>
    </div>
  );
}
