import { useState } from 'react';
import { Link } from 'react-router';
import {
  CreditCard, ChevronLeft, AlertCircle, CheckCircle,
  ChevronRight, ChevronDown, DollarSign, Calendar,
  Shield, Clock, Receipt, Building2, X,
} from 'lucide-react';

interface Bill {
  id: string;
  hospital: string;
  department: string;
  billDate: string;
  dueDate: string;
  amount: number;
  status: 'outstanding' | 'overdue' | 'paid';
  billRef: string;
  description: string;
}

const BILLS: Bill[] = [
  {
    id: '1',
    hospital: 'Clementi Polyclinic',
    department: 'General Practice Consultation',
    billDate: '5 Feb 2026',
    dueDate: '5 Mar 2026',
    amount: 15.20,
    status: 'outstanding',
    billRef: 'CP-2026-00892',
    description: 'Subsidised consultation fee — after Medisave claim',
  },
  {
    id: '2',
    hospital: 'Singapore General Hospital',
    department: 'Cardiology Outpatient',
    billDate: '12 Jan 2026',
    dueDate: '12 Feb 2026',
    amount: 234.50,
    status: 'overdue',
    billRef: 'SGH-2026-04521',
    description: 'Specialist consultation + ECG + Echocardiogram',
  },
  {
    id: '3',
    hospital: 'Tan Tock Seng Hospital',
    department: 'Laboratory Services',
    billDate: '20 Jan 2026',
    dueDate: '20 Feb 2026',
    amount: 45.00,
    status: 'outstanding',
    billRef: 'TTSH-2026-03341',
    description: 'Lipid panel + HbA1c + Kidney function tests',
  },
];

const PAID_BILLS = [
  { id: 'p1', hospital: 'Clementi Polyclinic', description: 'Consultation', date: '5 Nov 2025', amount: 12.30, ref: 'CP-2025-10532' },
  { id: 'p2', hospital: 'SGH', description: 'Cardiology Follow-up', date: '3 Oct 2025', amount: 188.00, ref: 'SGH-2025-09812' },
  { id: 'p3', hospital: 'NUH', description: 'Eye Clinic Consult', date: '15 Sep 2025', amount: 92.50, ref: 'NUH-2025-08234' },
];

const STATUS_CONFIG = {
  outstanding: { label: 'Outstanding', color: '#92400E', bg: '#FEF3C7', border: '#FCD34D' },
  overdue: { label: 'Overdue', color: '#991B1B', bg: '#FEE2E2', border: '#FCA5A5' },
  paid: { label: 'Paid', color: '#065F46', bg: '#D1FAE5', border: '#6EE7B7' },
};

export function PaymentsPage() {
  const [showHistory, setShowHistory] = useState(false);
  const [payingId, setPayingId] = useState<string | null>(null);
  const [paidIds, setPaidIds] = useState<Set<string>>(new Set());

  const outstanding = BILLS.filter((b) => !paidIds.has(b.id));
  const totalOutstanding = outstanding.reduce((sum, b) => sum + b.amount, 0);

  const handlePay = (id: string) => {
    setPayingId(id);
  };

  const confirmPay = () => {
    if (payingId) {
      setPaidIds((prev) => new Set([...prev, payingId]));
      setPayingId(null);
    }
  };

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
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Payments</h1>
          <p className="text-gray-500 text-sm">Manage your medical bills securely</p>
        </div>
      </div>

      {/* Total Outstanding Card */}
      <div
        className="rounded-2xl p-6 mb-5 text-white"
        style={{ background: 'linear-gradient(135deg, #1B6B45 0%, #155233 100%)' }}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <DollarSign size={20} className="opacity-80" />
            <span className="opacity-90 text-sm font-medium">Total Outstanding</span>
          </div>
          <Shield size={20} className="opacity-60" />
        </div>
        <p className="text-4xl font-bold mb-1">
          S$ {totalOutstanding.toFixed(2)}
        </p>
        <p className="text-sm opacity-80">
          {outstanding.length} bill{outstanding.length !== 1 ? 's' : ''} require{outstanding.length === 1 ? 's' : ''} payment
        </p>
        <div className="mt-4 flex gap-3">
          <button
            onClick={() => {
              if (outstanding.length > 0) setPayingId(outstanding[0].id);
            }}
            className="flex-1 bg-white py-3 rounded-xl font-semibold text-sm hover:bg-gray-50 transition-colors"
            style={{ color: '#1B6B45' }}
          >
            Pay All Bills
          </button>
          <button className="px-4 py-3 rounded-xl border border-white/30 text-white text-sm hover:bg-white/10">
            GIRO Setup
          </button>
        </div>
      </div>

      {/* Overdue Alert */}
      {outstanding.some((b) => b.status === 'overdue') && (
        <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl p-4 mb-5">
          <AlertCircle size={18} className="text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-red-800 font-medium text-sm">You have overdue bills</p>
            <p className="text-red-700 text-xs mt-0.5">
              Overdue bills may incur late payment fees. Please settle as soon as possible.
            </p>
          </div>
        </div>
      )}

      {/* Bills List */}
      <div className="mb-4">
        <h2 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <Receipt size={18} style={{ color: '#1B6B45' }} />
          Outstanding Bills
        </h2>

        <div className="space-y-3">
          {BILLS.map((bill) => {
            const isPaid = paidIds.has(bill.id);
            const statusCfg = isPaid ? STATUS_CONFIG.paid : STATUS_CONFIG[bill.status];

            return (
              <div
                key={bill.id}
                className={`bg-white rounded-2xl shadow-sm border overflow-hidden transition-all ${
                  isPaid ? 'opacity-60 border-gray-100' : 'border-gray-100'
                }`}
              >
                {/* Status accent bar */}
                <div
                  className="h-1"
                  style={{
                    backgroundColor: isPaid
                      ? '#16A34A'
                      : bill.status === 'overdue'
                      ? '#DC2626'
                      : '#D97706',
                  }}
                />

                <div className="p-5">
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex items-start gap-3">
                      <div
                        className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                        style={{ backgroundColor: '#E8F5EE' }}
                      >
                        <Building2 size={20} style={{ color: '#1B6B45' }} />
                      </div>
                      <div>
                        <h3 className="font-semibold text-gray-800">{bill.hospital}</h3>
                        <p className="text-sm text-gray-500">{bill.department}</p>
                        <p className="text-xs text-gray-400 mt-0.5">{bill.description}</p>
                      </div>
                    </div>
                    <span
                      className="text-xs font-medium px-2.5 py-1 rounded-full flex-shrink-0"
                      style={{ color: statusCfg.color, backgroundColor: statusCfg.bg }}
                    >
                      {isPaid ? 'Paid' : statusCfg.label}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mb-4 text-sm">
                    <div className="flex items-center gap-1.5 text-gray-500">
                      <Calendar size={13} />
                      <span>Billed: {bill.billDate}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-gray-500">
                      <Clock size={13} />
                      <span className={bill.status === 'overdue' && !isPaid ? 'text-red-600 font-medium' : ''}>
                        Due: {bill.dueDate}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 text-gray-400">
                      <Receipt size={13} />
                      <span className="text-xs">{bill.billRef}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs text-gray-400">Amount Due</p>
                      <p
                        className="text-2xl font-bold"
                        style={{ color: isPaid ? '#16A34A' : bill.status === 'overdue' ? '#DC2626' : '#1F2937' }}
                      >
                        S$ {bill.amount.toFixed(2)}
                      </p>
                    </div>

                    {isPaid ? (
                      <div className="flex items-center gap-1.5 text-green-600 font-medium">
                        <CheckCircle size={20} />
                        <span>Paid</span>
                      </div>
                    ) : (
                      <button
                        onClick={() => handlePay(bill.id)}
                        className="flex items-center gap-2 px-6 py-3 rounded-xl text-white font-semibold text-base shadow-sm hover:shadow-md active:scale-95 transition-all"
                        style={{
                          backgroundColor: bill.status === 'overdue' ? '#DC2626' : '#1B6B45',
                        }}
                      >
                        <CreditCard size={18} />
                        Pay Now
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {outstanding.length === 0 && (
            <div className="bg-green-50 border border-green-200 rounded-2xl p-8 text-center">
              <CheckCircle size={40} className="mx-auto text-green-500 mb-3" />
              <h3 className="font-bold text-green-800 text-lg mb-1">All bills paid! 🎉</h3>
              <p className="text-green-700 text-sm">You have no outstanding payments. Great job!</p>
            </div>
          )}
        </div>
      </div>

      {/* Payment Methods */}
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 mb-4">
        <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <CreditCard size={18} style={{ color: '#1B6B45' }} />
          Payment Methods
        </h3>
        <div className="space-y-2">
          {[
            { name: 'PayNow (NRIC/Mobile)', icon: '📱', available: true },
            { name: 'Medisave (CPF)', icon: '🏥', available: true },
            { name: 'Credit / Debit Card', icon: '💳', available: true },
            { name: 'GIRO (Auto-deduction)', icon: '🔄', available: false, action: 'Set Up' },
          ].map(({ name, icon, available, action }) => (
            <div key={name} className="flex items-center justify-between py-2">
              <div className="flex items-center gap-3">
                <span className="text-xl">{icon}</span>
                <span className="text-sm text-gray-700">{name}</span>
              </div>
              {action ? (
                <button className="text-xs font-medium px-3 py-1 rounded-lg border text-[#1B6B45] border-[#1B6B45] hover:bg-green-50">
                  {action}
                </button>
              ) : (
                <span className="text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full">Available</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Payment History */}
      <button
        className="w-full bg-white rounded-2xl p-4 shadow-sm border border-gray-100 flex items-center justify-between hover:bg-gray-50 transition-colors"
        onClick={() => setShowHistory(!showHistory)}
      >
        <div className="flex items-center gap-2 text-gray-700 font-medium">
          <Clock size={18} style={{ color: '#1B6B45' }} />
          Payment History
        </div>
        <ChevronDown
          size={18}
          className="text-gray-400 transition-transform"
          style={{ transform: showHistory ? 'rotate(180deg)' : 'rotate(0deg)' }}
        />
      </button>

      {showHistory && (
        <div className="mt-2 bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          {PAID_BILLS.map((bill, i) => (
            <div
              key={bill.id}
              className={`p-4 flex items-center justify-between ${
                i < PAID_BILLS.length - 1 ? 'border-b border-gray-100' : ''
              }`}
            >
              <div>
                <p className="font-medium text-gray-700 text-sm">{bill.hospital} — {bill.description}</p>
                <p className="text-xs text-gray-400 mt-0.5">{bill.date} · {bill.ref}</p>
              </div>
              <div className="text-right">
                <p className="font-semibold text-gray-800">S$ {bill.amount.toFixed(2)}</p>
                <p className="text-xs text-green-600 flex items-center justify-end gap-0.5 mt-0.5">
                  <CheckCircle size={10} /> Paid
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Payment Modal */}
      {payingId && (
        <div className="fixed inset-0 bg-black/60 flex items-end sm:items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-sm shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b">
              <h3 className="font-bold text-gray-800">Confirm Payment</h3>
              <button onClick={() => setPayingId(null)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <div className="p-5">
              {BILLS.find((b) => b.id === payingId) && (() => {
                const bill = BILLS.find((b) => b.id === payingId)!;
                return (
                  <>
                    <div className="bg-gray-50 rounded-xl p-4 mb-4">
                      <p className="text-sm text-gray-500 mb-1">{bill.hospital}</p>
                      <p className="font-medium text-gray-700 text-sm mb-3">{bill.department}</p>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Amount</span>
                        <span className="font-bold text-gray-800">S$ {bill.amount.toFixed(2)}</span>
                      </div>
                    </div>
                    <p className="text-xs text-gray-500 mb-4 text-center">
                      <Shield size={12} className="inline mr-1" />
                      Payment secured by Singpass · Ref: {bill.billRef}
                    </p>
                    <div className="space-y-2">
                      <button
                        onClick={confirmPay}
                        className="w-full py-3.5 rounded-xl text-white font-semibold"
                        style={{ backgroundColor: '#1B6B45' }}
                      >
                        📱 Pay via PayNow — S$ {bill.amount.toFixed(2)}
                      </button>
                      <button
                        onClick={confirmPay}
                        className="w-full py-3.5 rounded-xl font-medium text-gray-700 border border-gray-200 hover:bg-gray-50"
                      >
                        💳 Pay by Card
                      </button>
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
