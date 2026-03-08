import { useState, useMemo } from 'react';
import { Link } from 'react-router';
import {
  Calendar, ChevronLeft, MapPin, Clock, User,
  Plus, ChevronRight, Phone, Navigation, Bell,
  CheckCircle, AlertCircle, XCircle, ChevronDown,
  Search, Syringe, Stethoscope, Eye, Heart, Brain,
  Baby, Activity, Smile, Bone, Wifi, WifiOff,
  ArrowRight, Star, Globe, Languages, Info,
  ShieldCheck, Loader, X, Radio,
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Appointment {
  id: string;
  hospital: string;
  department: string;
  doctor: string;
  date: string;
  time: string;
  address: string;
  status: 'upcoming' | 'confirmed' | 'cancelled';
  reminderSet: boolean;
  phone: string;
  notes?: string;
  color: string;
  initials: string;
  queueEligible: boolean;
  checkedIn?: boolean;
}

// ─── Static Data ──────────────────────────────────────────────────────────────

const APPOINTMENTS: Appointment[] = [
  {
    id: '1',
    hospital: 'Singapore General Hospital',
    department: 'Cardiology',
    doctor: 'Dr. Lee Cheng Hwa',
    date: 'Saturday, 15 March 2026',
    time: '9:30 AM',
    address: 'Outram Road, Block 3 Level 2, Singapore 169608',
    status: 'confirmed',
    reminderSet: true,
    phone: '6321 4311',
    notes: 'Please bring your NRIC and previous ECG report. Fast 8 hours before blood test.',
    color: '#1B6B45',
    initials: 'SGH',
    queueEligible: true,
  },
  {
    id: '2',
    hospital: 'National University Hospital',
    department: 'Eye Clinic (Ophthalmology)',
    doctor: 'Dr. Wong Mei Lin',
    date: 'Sunday, 22 March 2026',
    time: '2:00 PM',
    address: '5 Lower Kent Ridge Road, Singapore 119074',
    status: 'upcoming',
    reminderSet: false,
    phone: '6779 5555',
    notes: 'Your eyes will be dilated — arrange for someone to drive you home.',
    color: '#1D4ED8',
    initials: 'NUH',
    queueEligible: false,
  },
  {
    id: '3',
    hospital: 'Clementi Polyclinic',
    department: 'General Practice',
    doctor: 'Dr. Rajesh Kumar',
    date: 'Sunday, 5 April 2026',
    time: '10:15 AM',
    address: '451 Clementi Ave 3, #01-01, Singapore 120451',
    status: 'upcoming',
    reminderSet: true,
    phone: '6391 6100',
    notes: 'Routine follow-up for diabetes management. Bring medication log.',
    color: '#7C3AED',
    initials: 'CP',
    queueEligible: true,
  },
];

const PAST_APPOINTMENTS = [
  { id: 'p1', hospital: 'Clementi Polyclinic', department: 'General Practice', doctor: 'Dr. Rajesh Kumar', date: '5 Feb 2026', status: 'completed' },
  { id: 'p2', hospital: 'Singapore General Hospital', department: 'Cardiology', doctor: 'Dr. Lee Cheng Hwa', date: '12 Jan 2026', status: 'completed' },
];

const STATUS_CONFIG = {
  upcoming: { label: 'Upcoming', icon: Clock, color: '#1D4ED8', bg: '#EFF6FF' },
  confirmed: { label: 'Confirmed', icon: CheckCircle, color: '#065F46', bg: '#D1FAE5' },
  cancelled: { label: 'Cancelled', icon: XCircle, color: '#991B1B', bg: '#FEE2E2' },
};

const PATIENTS = [
  { id: 'self', name: 'Tan Ah Kow (You)', nric: 'T**XX930C', relation: 'Self', dob: '15 Mar 1952' },
  { id: 'son', name: 'Tan Wei Ming', nric: 'T**YY123A', relation: 'Son', dob: '3 Jun 1980' },
  { id: 'daughter', name: 'Tan Siew Lian', nric: 'T**ZZ456B', relation: 'Daughter', dob: '12 Sep 1983' },
];

const INSTITUTIONS = [
  { id: 'sgh', name: 'Singapore General Hospital', short: 'SGH', type: 'Hospital', address: 'Outram Road, Singapore', color: '#1B6B45' },
  { id: 'nuh', name: 'National University Hospital', short: 'NUH', type: 'Hospital', address: 'Lower Kent Ridge Road, Singapore', color: '#1D4ED8' },
  { id: 'ktph', name: 'Khoo Teck Puat Hospital', short: 'KTPH', type: 'Hospital', address: 'Yishun Central, Singapore', color: '#7C3AED' },
  { id: 'ttsh', name: 'Tan Tock Seng Hospital', short: 'TTSH', type: 'Hospital', address: 'Moulmein Road, Singapore', color: '#B45309' },
  { id: 'cp', name: 'Clementi Polyclinic', short: 'CP', type: 'Polyclinic', address: '451 Clementi Ave 3, Singapore', color: '#0369A1' },
  { id: 'bp', name: 'Buona Vista Polyclinic', short: 'BVP', type: 'Polyclinic', address: 'Holland Drive, Singapore', color: '#0369A1' },
  { id: 'jp', name: 'Jurong Polyclinic', short: 'JP', type: 'Polyclinic', address: 'Jurong West, Singapore', color: '#0369A1' },
];

interface Specialty {
  id: string;
  name: string;
  icon: React.FC<{ size?: number; className?: string; style?: React.CSSProperties }>;
  color: string;
  isVaccination?: boolean;
  prepNote?: string;
  vaccineBadge?: string;
}

const SPECIALTIES: Specialty[] = [
  { id: 'cardiology', name: 'Cardiology', icon: Heart, color: '#DC2626', prepNote: 'Fast for 8 hours before blood work. Bring previous ECG reports and your medication list.' },
  { id: 'ophthalmology', name: 'Eye Clinic (Ophthalmology)', icon: Eye, color: '#1D4ED8', prepNote: 'Eyes may be dilated during examination. Arrange transport — do not drive after.' },
  { id: 'gp', name: 'General Practice', icon: Stethoscope, color: '#1B6B45', prepNote: 'Bring your NRIC and current medication log. Arrive 10 minutes early.' },
  { id: 'neurology', name: 'Neurology', icon: Brain, color: '#7C3AED', prepNote: 'No special preparation needed. Bring a list of symptoms and frequency of occurrence.' },
  { id: 'dental', name: 'Dental', icon: Smile, color: '#0369A1', prepNote: 'Brush and floss before your appointment. Inform the dentist of any allergies.' },
  { id: 'ortho', name: 'Orthopaedics', icon: Bone, color: '#92400E', prepNote: 'Bring previous X-ray or MRI images if available. Wear loose-fitting clothing.' },
  { id: 'paeds', name: 'Paediatrics', icon: Baby, color: '#EC4899', prepNote: "Bring the child's health booklet and immunisation records." },
  { id: 'vaccination', name: 'Vaccination', icon: Syringe, color: '#059669', isVaccination: true, prepNote: 'Stay for 15–30 minutes after injection for observation. Wear a sleeveless top for easy access.', vaccineBadge: 'Booster Dose' },
];

const DOCTORS: Record<string, { id: string; name: string; title: string; experience: string; lang: string[]; rating: number; slots: number }[]> = {
  cardiology: [
    { id: 'd1', name: 'Dr. Lee Cheng Hwa', title: 'Senior Consultant', experience: '22 years', lang: ['English', '中文'], rating: 4.9, slots: 3 },
    { id: 'd2', name: 'Dr. Priya Nair', title: 'Consultant', experience: '14 years', lang: ['English', 'தமிழ்'], rating: 4.7, slots: 5 },
  ],
  ophthalmology: [
    { id: 'd3', name: 'Dr. Wong Mei Lin', title: 'Associate Consultant', experience: '10 years', lang: ['English', '中文'], rating: 4.8, slots: 4 },
  ],
  gp: [
    { id: 'd4', name: 'Dr. Rajesh Kumar', title: 'Medical Officer', experience: '8 years', lang: ['English', 'Melayu', 'தமிழ்'], rating: 4.6, slots: 6 },
    { id: 'd5', name: 'Dr. Tan Hui Ling', title: 'Medical Officer', experience: '6 years', lang: ['English', '中文'], rating: 4.5, slots: 8 },
  ],
  vaccination: [
    { id: 'd6', name: 'Any Available Nurse / MO', title: 'Vaccination Clinic', experience: 'Walk-in or appointment', lang: ['English', '中文', 'Melayu', 'தமிழ்'], rating: 4.8, slots: 12 },
  ],
  neurology: [
    { id: 'd7', name: 'Dr. Suresh Babu', title: 'Senior Consultant', experience: '18 years', lang: ['English', 'தமிழ்'], rating: 4.7, slots: 2 },
  ],
  dental: [
    { id: 'd8', name: 'Dr. Amelia Tan', title: 'Dental Surgeon', experience: '9 years', lang: ['English', '中文'], rating: 4.6, slots: 5 },
  ],
  ortho: [
    { id: 'd9', name: 'Dr. Ahmad Farid', title: 'Consultant', experience: '16 years', lang: ['English', 'Melayu'], rating: 4.8, slots: 3 },
  ],
  paeds: [
    { id: 'd10', name: 'Dr. Grace Lim', title: 'Senior Consultant', experience: '20 years', lang: ['English', '中文'], rating: 4.9, slots: 4 },
  ],
};

const VISIT_REASONS = [
  'Follow-up consultation', 'Acute pain or discomfort', 'Routine check-up',
  'Prescription renewal', 'Flu jab / Vaccination', 'Pre-surgery assessment',
  'Specialist referral', 'Lab test results review',
];

// Calendar helpers
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}
function getFirstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay();
}

// Deterministic slot availability (based on day)
function getSlotsForDay(day: number): { morning: string[]; afternoon: string[] } {
  const morningAll = ['8:00 AM', '8:30 AM', '9:00 AM', '9:30 AM', '10:00 AM', '10:30 AM', '11:00 AM', '11:30 AM'];
  const afternoonAll = ['1:00 PM', '1:30 PM', '2:00 PM', '2:30 PM', '3:00 PM', '3:30 PM', '4:00 PM', '4:30 PM'];
  const seed = day % 5;
  const morning = morningAll.filter((_, i) => (i + seed) % 3 !== 0);
  const afternoon = afternoonAll.filter((_, i) => (i + seed) % 4 !== 1);
  return { morning, afternoon };
}

// ─── Main Component ────────────────────────────────────────────────────────────

type MainTab = 'upcoming' | 'past' | 'book';

export function AppointmentsPage() {
  const [mainTab, setMainTab] = useState<MainTab>('upcoming');
  const [reminders, setReminders] = useState<Record<string, boolean>>(
    Object.fromEntries(APPOINTMENTS.map((a) => [a.id, a.reminderSet]))
  );
  const [checkedIn, setCheckedIn] = useState<Record<string, boolean>>({});
  const [checkingIn, setCheckingIn] = useState<string | null>(null);

  const toggleReminder = (id: string) => setReminders((prev) => ({ ...prev, [id]: !prev[id] }));

  const handleCheckIn = (id: string) => {
    setCheckingIn(id);
    setTimeout(() => {
      setCheckedIn((prev) => ({ ...prev, [id]: true }));
      setCheckingIn(null);
    }, 2000);
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <Link to="/app" className="w-10 h-10 rounded-xl flex items-center justify-center hover:bg-gray-200 bg-white shadow-sm border border-gray-100">
          <ChevronLeft size={20} className="text-gray-600" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-800">Appointments</h1>
          <p className="text-gray-500 text-sm">Manage and book your medical visits</p>
        </div>
        <button
          onClick={() => setMainTab('book')}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-white text-sm shadow-sm"
          style={{ backgroundColor: '#1B6B45' }}
        >
          <Plus size={16} />
          <span className="hidden sm:inline">Book New</span>
        </button>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        {[
          { label: 'Upcoming', value: '3', color: '#1B6B45', bg: '#E8F5EE' },
          { label: 'This Month', value: '2', color: '#1D4ED8', bg: '#EFF6FF' },
          { label: 'Past 90 Days', value: '5', color: '#7C3AED', bg: '#F5F3FF' },
        ].map(({ label, value, color, bg }) => (
          <div key={label} className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 text-center">
            <p className="text-2xl font-bold" style={{ color }}>{value}</p>
            <p className="text-xs text-gray-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Main Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 mb-6">
        {[
          { key: 'upcoming', label: 'Upcoming (3)' },
          { key: 'past', label: 'Past (2)' },
          { key: 'book', label: '+ Book New' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setMainTab(key as MainTab)}
            className="flex-1 py-2.5 rounded-lg text-sm transition-all"
            style={
              mainTab === key
                ? { backgroundColor: key === 'book' ? '#1B6B45' : 'white', color: key === 'book' ? 'white' : '#1B6B45', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', fontWeight: 600 }
                : { color: '#6B7280', fontWeight: 500 }
            }
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Upcoming Tab ── */}
      {mainTab === 'upcoming' && (
        <div className="relative">
          <div className="absolute left-[28px] top-8 bottom-8 w-0.5 hidden sm:block" style={{ backgroundColor: '#D1D5DB' }} />
          <div className="space-y-4">
            {APPOINTMENTS.map((appt) => {
              const statusCfg = STATUS_CONFIG[appt.status];
              const StatusIcon = statusCfg.icon;
              const hasReminder = reminders[appt.id];
              const isCheckedIn = checkedIn[appt.id];
              const isCheckingInNow = checkingIn === appt.id;

              return (
                <div key={appt.id} className="flex gap-4">
                  <div className="hidden sm:flex flex-col items-center flex-shrink-0 w-14">
                    <div className="w-14 h-14 rounded-full flex items-center justify-center text-white font-bold text-sm shadow-md z-10 flex-shrink-0" style={{ backgroundColor: appt.color }}>
                      {appt.initials}
                    </div>
                  </div>
                  <div className="flex-1 bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                    <div className="h-1.5" style={{ backgroundColor: appt.color }} />
                    <div className="p-5">
                      <div className="flex items-start justify-between gap-2 mb-3">
                        <div>
                          <h3 className="font-bold text-gray-800 text-base">{appt.hospital}</h3>
                          <p className="text-sm" style={{ color: appt.color }}>{appt.department}</p>
                        </div>
                        <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full flex-shrink-0" style={{ color: statusCfg.color, backgroundColor: statusCfg.bg }}>
                          <StatusIcon size={11} />
                          {statusCfg.label}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
                        <div className="flex items-center gap-2 text-sm text-gray-600"><Calendar size={15} style={{ color: '#1B6B45' }} /><span>{appt.date}</span></div>
                        <div className="flex items-center gap-2 text-sm text-gray-600"><Clock size={15} style={{ color: '#1B6B45' }} /><span>{appt.time}</span></div>
                        <div className="flex items-center gap-2 text-sm text-gray-600"><User size={15} style={{ color: '#1B6B45' }} /><span>{appt.doctor}</span></div>
                        <div className="flex items-center gap-2 text-sm text-gray-600"><Phone size={15} style={{ color: '#1B6B45' }} /><span>{appt.phone}</span></div>
                      </div>

                      <div className="flex items-start gap-2 text-sm text-gray-500 mb-3">
                        <MapPin size={14} className="flex-shrink-0 mt-0.5" style={{ color: '#1B6B45' }} />
                        <span>{appt.address}</span>
                      </div>

                      {appt.notes && (
                        <div className="bg-amber-50 border border-amber-100 rounded-xl px-4 py-3 mb-4 flex items-start gap-2">
                          <AlertCircle size={15} className="text-amber-600 flex-shrink-0 mt-0.5" />
                          <p className="text-sm text-amber-800">{appt.notes}</p>
                        </div>
                      )}

                      {/* Digital Queue Check-in */}
                      {appt.queueEligible && (
                        <div className={`rounded-xl px-4 py-3 mb-4 flex items-center gap-3 border transition-all ${isCheckedIn ? 'bg-green-50 border-green-200' : 'bg-blue-50 border-blue-200'}`}>
                          {isCheckingInNow ? (
                            <Loader size={16} className="text-blue-600 animate-spin flex-shrink-0" />
                          ) : isCheckedIn ? (
                            <CheckCircle size={16} className="text-green-600 flex-shrink-0" />
                          ) : (
                            <Wifi size={16} className="text-blue-600 flex-shrink-0" />
                          )}
                          <div className="flex-1">
                            {isCheckedIn ? (
                              <>
                                <p className="text-sm font-semibold text-green-800">Checked in — Queue No. B47</p>
                                <p className="text-xs text-green-700">Est. wait: ~12 minutes. Please proceed to Level 2.</p>
                              </>
                            ) : (
                              <>
                                <p className="text-sm font-semibold text-blue-800">Digital Queue Check-in</p>
                                <p className="text-xs text-blue-700">Available when you're within 500m of the clinic.</p>
                              </>
                            )}
                          </div>
                          {!isCheckedIn && (
                            <button
                              onClick={() => handleCheckIn(appt.id)}
                              disabled={isCheckingInNow}
                              className="px-3 py-1.5 rounded-lg text-white text-xs font-semibold flex-shrink-0 transition-all disabled:opacity-70"
                              style={{ backgroundColor: '#1D4ED8' }}
                            >
                              {isCheckingInNow ? 'Locating…' : 'Check In'}
                            </button>
                          )}
                        </div>
                      )}

                      <div className="flex flex-wrap gap-2">
                        <button className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-white text-sm" style={{ backgroundColor: '#1B6B45' }}>
                          <Navigation size={15} />
                          Directions
                        </button>
                        <button
                          onClick={() => toggleReminder(appt.id)}
                          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm border transition-colors"
                          style={hasReminder ? { backgroundColor: '#E8F5EE', color: '#1B6B45', borderColor: '#1B6B45' } : { backgroundColor: 'white', color: '#6B7280', borderColor: '#E5E7EB' }}
                        >
                          <Bell size={15} />
                          {hasReminder ? 'Reminder Set ✓' : 'Set Reminder'}
                        </button>
                        <button className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm border border-gray-200 text-gray-600 hover:bg-gray-50 ml-auto">
                          Reschedule <ChevronRight size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-6 rounded-2xl p-5 text-center" style={{ background: 'linear-gradient(135deg, #E8F5EE 0%, #D1FAE5 100%)' }}>
            <Calendar size={32} className="mx-auto mb-2" style={{ color: '#1B6B45' }} />
            <h3 className="font-semibold text-gray-800 mb-1">Need another appointment?</h3>
            <p className="text-sm text-gray-600 mb-4">Book specialist or polyclinic visits online without calling.</p>
            <button onClick={() => setMainTab('book')} className="px-6 py-3 rounded-xl text-white" style={{ backgroundColor: '#1B6B45' }}>
              <Plus size={16} className="inline mr-2" />Make New Appointment
            </button>
          </div>
        </div>
      )}

      {/* ── Past Tab ── */}
      {mainTab === 'past' && (
        <div className="space-y-3">
          {PAST_APPOINTMENTS.map((appt) => (
            <div key={appt.id} className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-gray-700">{appt.hospital}</h3>
                  <p className="text-sm text-gray-500">{appt.department} · {appt.doctor}</p>
                  <p className="text-xs text-gray-400 mt-1 flex items-center gap-1"><Calendar size={11} />{appt.date}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-green-700 bg-green-50 px-2.5 py-1 rounded-full flex items-center gap-1">
                    <CheckCircle size={11} /> Completed
                  </span>
                  <button className="text-gray-400 hover:text-[#1B6B45]"><ChevronRight size={18} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Book New Tab ── */}
      {mainTab === 'book' && (
        <BookingForm onSuccess={() => setMainTab('upcoming')} />
      )}
    </div>
  );
}

// ─── Booking Form (Multi-Step) ─────────────────────────────────────────────────

function BookingForm({ onSuccess }: { onSuccess: () => void }) {
  const [step, setStep] = useState(1);
  const TOTAL_STEPS = 4;

  // Form state
  const [selectedPatient, setSelectedPatient] = useState(PATIENTS[0]);
  const [patientOpen, setPatientOpen] = useState(false);
  const [institutionSearch, setInstitutionSearch] = useState('');
  const [selectedInstitution, setSelectedInstitution] = useState<typeof INSTITUTIONS[0] | null>(null);
  const [selectedSpecialty, setSelectedSpecialty] = useState<Specialty | null>(null);
  const [selectedDoctor, setSelectedDoctor] = useState<string>('any');

  // Calendar
  const today = new Date(2026, 2, 8); // March 8 2026
  const [calYear, setCalYear] = useState(today.getFullYear());
  const [calMonth, setCalMonth] = useState(today.getMonth());
  const [selectedDate, setSelectedDate] = useState<number | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);

  // Visit
  const [visitReason, setVisitReason] = useState('');
  const [reasonChip, setReasonChip] = useState<string | null>(null);
  const [notes, setNotes] = useState('');

  // Confirmation state
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const filteredInstitutions = INSTITUTIONS.filter((i) =>
    i.name.toLowerCase().includes(institutionSearch.toLowerCase()) ||
    i.short.toLowerCase().includes(institutionSearch.toLowerCase())
  );

  const slots = useMemo(() => selectedDate ? getSlotsForDay(selectedDate) : { morning: [], afternoon: [] }, [selectedDate]);

  const availableDoctors = selectedSpecialty ? (DOCTORS[selectedSpecialty.id] ?? []) : [];

  const daysInMonth = getDaysInMonth(calYear, calMonth);
  const firstDay = getFirstDayOfMonth(calYear, calMonth);

  const prevMonth = () => {
    if (calMonth === 0) { setCalYear(y => y - 1); setCalMonth(11); }
    else setCalMonth(m => m - 1);
    setSelectedDate(null); setSelectedSlot(null);
  };
  const nextMonth = () => {
    if (calMonth === 11) { setCalYear(y => y + 1); setCalMonth(0); }
    else setCalMonth(m => m + 1);
    setSelectedDate(null); setSelectedSlot(null);
  };

  const isDateDisabled = (day: number) => {
    const d = new Date(calYear, calMonth, day);
    return d < today || d.getDay() === 0; // Sundays closed
  };

  const canProceed = () => {
    if (step === 1) return selectedInstitution !== null && selectedSpecialty !== null;
    if (step === 2) return selectedDate !== null && selectedSlot !== null;
    if (step === 3) return visitReason.trim().length > 0 || reasonChip !== null;
    return true;
  };

  const handleSubmit = () => {
    setSubmitting(true);
    setTimeout(() => { setSubmitting(false); setSubmitted(true); }, 2000);
  };

  if (submitted) {
    return <ConfirmationScreen
      institution={selectedInstitution!}
      specialty={selectedSpecialty!}
      date={`${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(selectedDate).padStart(2, '0')}`}
      slot={selectedSlot!}
      patient={selectedPatient}
      onDone={onSuccess}
    />;
  }

  return (
    <div>
      {/* Step Progress */}
      <StepProgress current={step} total={TOTAL_STEPS} labels={['Service', 'Date & Time', 'Details', 'Review']} />

      {/* ── STEP 1: Institution & Specialty ── */}
      {step === 1 && (
        <div className="space-y-5">
          {/* Patient selector */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
              <User size={15} style={{ color: '#1B6B45' }} /> Booking for
            </label>
            <div className="relative">
              <button
                onClick={() => setPatientOpen(!patientOpen)}
                className="w-full flex items-center justify-between px-4 py-3.5 bg-white border-2 rounded-xl text-left transition-colors"
                style={{ borderColor: patientOpen ? '#1B6B45' : '#E5E7EB' }}
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0" style={{ backgroundColor: '#1B6B45' }}>
                    {selectedPatient.name.charAt(0)}
                  </div>
                  <div>
                    <p className="font-semibold text-gray-800 text-sm">{selectedPatient.name}</p>
                    <p className="text-xs text-gray-500">{selectedPatient.relation} · {selectedPatient.nric}</p>
                  </div>
                </div>
                <ChevronDown size={16} className="text-gray-400 transition-transform" style={{ transform: patientOpen ? 'rotate(180deg)' : 'rotate(0deg)' }} />
              </button>
              {patientOpen && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-20 overflow-hidden">
                  {PATIENTS.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => { setSelectedPatient(p); setPatientOpen(false); }}
                      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-green-50 transition-colors border-b border-gray-50 last:border-0"
                    >
                      <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0" style={{ backgroundColor: p.id === selectedPatient.id ? '#1B6B45' : '#9CA3AF' }}>
                        {p.name.charAt(0)}
                      </div>
                      <div className="text-left flex-1">
                        <p className="font-semibold text-gray-800 text-sm">{p.name}</p>
                        <p className="text-xs text-gray-500">{p.relation} · DOB: {p.dob}</p>
                      </div>
                      {p.id === selectedPatient.id && <CheckCircle size={16} style={{ color: '#1B6B45' }} />}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Institution */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
              <MapPin size={15} style={{ color: '#1B6B45' }} /> Healthcare Institution
            </label>
            <div className="relative mb-2">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                className="w-full pl-10 pr-4 py-3 bg-white border-2 border-gray-200 rounded-xl text-sm focus:outline-none focus:border-[#1B6B45] transition-colors"
                placeholder="Search hospital or polyclinic…"
                value={institutionSearch}
                onChange={(e) => setInstitutionSearch(e.target.value)}
              />
            </div>

            {/* Institution type grouping */}
            {['Hospital', 'Polyclinic'].map((type) => {
              const items = filteredInstitutions.filter((i) => i.type === type);
              if (!items.length) return null;
              return (
                <div key={type} className="mb-3">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-1">{type}s</p>
                  <div className="space-y-2">
                    {items.map((inst) => (
                      <button
                        key={inst.id}
                        onClick={() => setSelectedInstitution(inst)}
                        className="w-full flex items-center gap-3 px-4 py-3.5 rounded-xl text-left transition-all border-2"
                        style={
                          selectedInstitution?.id === inst.id
                            ? { borderColor: inst.color, backgroundColor: `${inst.color}10` }
                            : { borderColor: '#E5E7EB', backgroundColor: 'white' }
                        }
                      >
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white text-xs font-bold flex-shrink-0" style={{ backgroundColor: inst.color }}>
                          {inst.short}
                        </div>
                        <div className="flex-1">
                          <p className="font-semibold text-gray-800 text-sm">{inst.name}</p>
                          <p className="text-xs text-gray-500">{inst.address}</p>
                        </div>
                        {selectedInstitution?.id === inst.id && (
                          <CheckCircle size={18} style={{ color: inst.color }} className="flex-shrink-0" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Specialty */}
          {selectedInstitution && (
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
                <Stethoscope size={15} style={{ color: '#1B6B45' }} /> Specialty / Department
              </label>
              <div className="grid grid-cols-2 gap-2">
                {SPECIALTIES.map((spec) => {
                  const Icon = spec.icon;
                  const selected = selectedSpecialty?.id === spec.id;
                  return (
                    <button
                      key={spec.id}
                      onClick={() => setSelectedSpecialty(spec)}
                      className="flex items-center gap-3 px-3 py-3.5 rounded-xl text-left transition-all border-2 relative"
                      style={selected ? { borderColor: spec.color, backgroundColor: `${spec.color}10` } : { borderColor: '#E5E7EB', backgroundColor: 'white' }}
                    >
                      <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${spec.color}18` }}>
                        <Icon size={18} style={{ color: spec.color }} />
                      </div>
                      <span className="text-sm font-medium text-gray-700">{spec.name}</span>
                      {spec.isVaccination && (
                        <span className="absolute -top-1.5 -right-1.5 bg-green-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                          VAX
                        </span>
                      )}
                      {selected && <CheckCircle size={14} style={{ color: spec.color }} className="ml-auto flex-shrink-0" />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Vaccination badge notice */}
          {selectedSpecialty?.isVaccination && (
            <div className="flex items-start gap-3 bg-green-50 border border-green-200 rounded-xl p-4">
              <Syringe size={18} className="text-green-700 flex-shrink-0 mt-0.5" />
              <div>
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <p className="text-sm font-semibold text-green-800">Vaccination Booking</p>
                  <span className="text-xs font-bold bg-green-600 text-white px-2 py-0.5 rounded-full flex items-center gap-1">
                    <ShieldCheck size={10} /> {selectedSpecialty.vaccineBadge}
                  </span>
                  <span className="text-xs font-semibold text-green-700 bg-green-100 border border-green-300 px-2 py-0.5 rounded-full">
                    MOH Recommended
                  </span>
                </div>
                <p className="text-xs text-green-700">This booking is for a vaccine booster dose. Bring your physical or digital immunisation booklet.</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── STEP 2: Date & Time ── */}
      {step === 2 && (
        <div className="space-y-5">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            {/* Calendar header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100" style={{ backgroundColor: '#1B6B45' }}>
              <button onClick={prevMonth} className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center text-white hover:bg-white/30">
                <ChevronLeft size={16} />
              </button>
              <p className="font-semibold text-white">{MONTH_NAMES[calMonth]} {calYear}</p>
              <button onClick={nextMonth} className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center text-white hover:bg-white/30">
                <ChevronRight size={16} />
              </button>
            </div>

            {/* Day headers */}
            <div className="grid grid-cols-7 border-b border-gray-100">
              {DAY_NAMES.map((d) => (
                <div key={d} className="py-2 text-center text-xs font-semibold text-gray-400">{d}</div>
              ))}
            </div>

            {/* Day cells */}
            <div className="grid grid-cols-7 p-3 gap-1">
              {Array.from({ length: firstDay }).map((_, i) => <div key={`e${i}`} />)}
              {Array.from({ length: daysInMonth }).map((_, i) => {
                const day = i + 1;
                const disabled = isDateDisabled(day);
                const selected = selectedDate === day;
                const isToday = day === today.getDate() && calMonth === today.getMonth() && calYear === today.getFullYear();
                const hasSlots = !disabled && getSlotsForDay(day).morning.length + getSlotsForDay(day).afternoon.length > 4;

                return (
                  <button
                    key={day}
                    onClick={() => { if (!disabled) { setSelectedDate(day); setSelectedSlot(null); } }}
                    disabled={disabled}
                    className="relative aspect-square rounded-xl flex flex-col items-center justify-center transition-all text-sm"
                    style={
                      selected
                        ? { backgroundColor: '#1B6B45', color: 'white' }
                        : disabled
                        ? { color: '#D1D5DB', cursor: 'not-allowed' }
                        : isToday
                        ? { backgroundColor: '#E8F5EE', color: '#1B6B45', fontWeight: 700 }
                        : { color: '#374151', ':hover': { backgroundColor: '#F3F4F6' } }
                    }
                  >
                    <span>{day}</span>
                    {hasSlots && !disabled && !selected && (
                      <span className="absolute bottom-1 w-1 h-1 rounded-full" style={{ backgroundColor: '#1B6B45' }} />
                    )}
                    {selected && hasSlots && (
                      <span className="absolute bottom-1 w-1 h-1 rounded-full bg-white/60" />
                    )}
                  </button>
                );
              })}
            </div>

            <div className="px-4 pb-3 flex items-center gap-4 text-xs text-gray-400">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: '#1B6B45' }} /> Available slots</span>
              <span className="flex items-center gap-1 text-gray-300"><span className="w-2 h-2 rounded-full inline-block bg-gray-200" /> Unavailable / Closed</span>
            </div>
          </div>

          {/* Time Slots */}
          {selectedDate && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-2 mb-4">
                <Clock size={16} style={{ color: '#1B6B45' }} />
                <p className="font-semibold text-gray-800">Available Slots — {MONTH_NAMES[calMonth]} {selectedDate}</p>
              </div>

              {/* Morning */}
              <div className="mb-4">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">🌅 Morning</p>
                {slots.morning.length > 0 ? (
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                    {slots.morning.map((slot) => (
                      <SlotButton key={slot} slot={slot} selected={selectedSlot === slot} onClick={() => setSelectedSlot(slot)} />
                    ))}
                    {/* Show a few greyed-out taken slots */}
                    {['8:30 AM', '9:00 AM'].filter(s => !slots.morning.includes(s)).slice(0, 2).map(s => (
                      <SlotButton key={`taken-${s}`} slot={s} selected={false} taken onClick={() => {}} />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400">No morning slots available.</p>
                )}
              </div>

              {/* Afternoon */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">🌆 Afternoon</p>
                {slots.afternoon.length > 0 ? (
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                    {slots.afternoon.map((slot) => (
                      <SlotButton key={slot} slot={slot} selected={selectedSlot === slot} onClick={() => setSelectedSlot(slot)} />
                    ))}
                    {['2:00 PM'].filter(s => !slots.afternoon.includes(s)).map(s => (
                      <SlotButton key={`taken-${s}`} slot={s} selected={false} taken onClick={() => {}} />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400">No afternoon slots available.</p>
                )}
              </div>

              {selectedSlot && (
                <div className="mt-4 flex items-center gap-2 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
                  <CheckCircle size={16} className="text-green-600" />
                  <p className="text-sm font-medium text-green-800">
                    Selected: {MONTH_NAMES[calMonth]} {selectedDate}, {calYear} at {selectedSlot}
                  </p>
                </div>
              )}
            </div>
          )}

          {!selectedDate && (
            <div className="flex items-center gap-2 bg-blue-50 border border-blue-100 rounded-xl p-4">
              <Info size={16} className="text-blue-500 flex-shrink-0" />
              <p className="text-sm text-blue-700">Select a date on the calendar above to view available slots. Sundays are closed.</p>
            </div>
          )}
        </div>
      )}

      {/* ── STEP 3: Details ── */}
      {step === 3 && (
        <div className="space-y-5">
          {/* Doctor selection */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
              <User size={15} style={{ color: '#1B6B45' }} /> Preferred Doctor <span className="text-gray-400 font-normal">(Optional)</span>
            </label>
            <div className="space-y-2">
              <button
                onClick={() => setSelectedDoctor('any')}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left border-2 transition-all"
                style={selectedDoctor === 'any' ? { borderColor: '#1B6B45', backgroundColor: '#E8F5EE' } : { borderColor: '#E5E7EB', backgroundColor: 'white' }}
              >
                <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                  <User size={18} className="text-gray-500" />
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-gray-800 text-sm">Any Available Doctor</p>
                  <p className="text-xs text-gray-500">Assigned automatically — earliest available</p>
                </div>
                {selectedDoctor === 'any' && <CheckCircle size={16} style={{ color: '#1B6B45' }} />}
              </button>

              {availableDoctors.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => setSelectedDoctor(doc.id)}
                  className="w-full flex items-center gap-3 px-4 py-3.5 rounded-xl text-left border-2 transition-all"
                  style={selectedDoctor === doc.id ? { borderColor: '#1B6B45', backgroundColor: '#E8F5EE' } : { borderColor: '#E5E7EB', backgroundColor: 'white' }}
                >
                  <div className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0" style={{ backgroundColor: '#1B6B45' }}>
                    {doc.name.split(' ').pop()?.charAt(0)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-semibold text-gray-800 text-sm">{doc.name}</p>
                      <div className="flex items-center gap-0.5 text-amber-400">
                        <Star size={11} fill="currentColor" />
                        <span className="text-xs text-gray-500">{doc.rating}</span>
                      </div>
                    </div>
                    <p className="text-xs text-gray-500">{doc.title} · {doc.experience}</p>
                    <div className="flex items-center gap-1 mt-1">
                      <Languages size={11} className="text-gray-400" />
                      <span className="text-xs text-gray-400">{doc.lang.join(', ')}</span>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-xs text-green-600 font-medium">{doc.slots} slots</p>
                    <p className="text-xs text-gray-400">available</p>
                    {selectedDoctor === doc.id && <CheckCircle size={14} style={{ color: '#1B6B45' }} className="mt-1 ml-auto" />}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Reason chips */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
              <Activity size={15} style={{ color: '#1B6B45' }} /> Reason for Visit <span className="text-red-400">*</span>
            </label>
            <div className="flex flex-wrap gap-2 mb-3">
              {VISIT_REASONS.map((r) => (
                <button
                  key={r}
                  onClick={() => { setReasonChip(r === reasonChip ? null : r); setVisitReason(''); }}
                  className="px-3 py-1.5 rounded-full text-sm border-2 transition-all"
                  style={reasonChip === r ? { borderColor: '#1B6B45', backgroundColor: '#E8F5EE', color: '#1B6B45', fontWeight: 600 } : { borderColor: '#E5E7EB', backgroundColor: 'white', color: '#6B7280' }}
                >
                  {r}
                </button>
              ))}
            </div>
            <textarea
              rows={3}
              className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl text-sm focus:outline-none focus:border-[#1B6B45] transition-colors resize-none"
              placeholder="Or describe your reason in your own words…"
              value={visitReason}
              onChange={(e) => { setVisitReason(e.target.value); setReasonChip(null); }}
            />
          </div>

          {/* Additional notes */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Additional Notes <span className="text-gray-400 font-normal">(Optional)</span></label>
            <textarea
              rows={2}
              className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl text-sm focus:outline-none focus:border-[#1B6B45] transition-colors resize-none"
              placeholder="E.g. I need a wheelchair-accessible room, or please send an SMS reminder 2 days before."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          {/* Preparation instructions */}
          {selectedSpecialty?.prepNote && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle size={15} className="text-amber-600" />
                <p className="text-sm font-semibold text-amber-800">Preparation Instructions</p>
              </div>
              <p className="text-sm text-amber-700">{selectedSpecialty.prepNote}</p>
            </div>
          )}
        </div>
      )}

      {/* ── STEP 4: Review & Confirm ── */}
      {step === 4 && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100" style={{ backgroundColor: '#1B6B45' }}>
              <p className="text-white font-semibold">Review Your Appointment</p>
              <p className="text-green-200 text-xs mt-0.5">Please confirm all details before submitting.</p>
            </div>

            <div className="divide-y divide-gray-50">
              <ReviewRow icon={<User size={15} style={{ color: '#1B6B45' }} />} label="Patient" value={`${selectedPatient.name} (${selectedPatient.relation})`} />
              <ReviewRow icon={<MapPin size={15} style={{ color: '#1B6B45' }} />} label="Institution" value={selectedInstitution?.name ?? '—'} />
              <ReviewRow icon={<Stethoscope size={15} style={{ color: '#1B6B45' }} />} label="Specialty" value={selectedSpecialty?.name ?? '—'} />
              <ReviewRow icon={<Calendar size={15} style={{ color: '#1B6B45' }} />} label="Date" value={selectedDate ? `${MONTH_NAMES[calMonth]} ${selectedDate}, ${calYear}` : '—'} />
              <ReviewRow icon={<Clock size={15} style={{ color: '#1B6B45' }} />} label="Time" value={selectedSlot ?? '—'} />
              <ReviewRow
                icon={<User size={15} style={{ color: '#1B6B45' }} />}
                label="Doctor"
                value={selectedDoctor === 'any' ? 'Any Available Doctor' : availableDoctors.find(d => d.id === selectedDoctor)?.name ?? '—'}
              />
              <ReviewRow icon={<Activity size={15} style={{ color: '#1B6B45' }} />} label="Reason" value={reasonChip ?? visitReason ?? '—'} />
            </div>
          </div>

          {/* Vaccination badge on review */}
          {selectedSpecialty?.isVaccination && (
            <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl p-4">
              <Syringe size={18} className="text-green-700 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-green-800">Vaccination — {selectedSpecialty.vaccineBadge}</p>
                <p className="text-xs text-green-700 mt-0.5">Your vaccination record will be updated in your Health Booklet after the dose.</p>
              </div>
              <span className="flex-shrink-0 text-xs font-bold bg-green-600 text-white px-2 py-1 rounded-full flex items-center gap-1">
                <ShieldCheck size={10} /> Verified
              </span>
            </div>
          )}

          {/* Prep reminder */}
          {selectedSpecialty?.prepNote && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
              <AlertCircle size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-amber-800 mb-1">Preparation Reminder</p>
                <p className="text-sm text-amber-700">{selectedSpecialty.prepNote}</p>
              </div>
            </div>
          )}

          {/* Digital queue info */}
          <div className="flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-xl p-4">
            <Wifi size={16} className="text-blue-600 flex-shrink-0" />
            <p className="text-sm text-blue-700">
              <strong>Digital queue check-in</strong> will be available on the day of your appointment when you're within 500m of the clinic.
            </p>
          </div>

          {/* Consent */}
          <div className="flex items-start gap-3 bg-gray-50 border border-gray-200 rounded-xl p-4">
            <ShieldCheck size={16} className="text-gray-500 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-gray-600">
              By confirming, you agree to receive appointment reminders via SMS and email. Your data is protected under the Singapore Personal Data Protection Act.
            </p>
          </div>

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full py-4 rounded-2xl text-white font-semibold text-base flex items-center justify-center gap-3 transition-all disabled:opacity-80"
            style={{ background: 'linear-gradient(135deg, #1B9A7A 0%, #1B6B45 100%)' }}
          >
            {submitting ? (
              <>
                <Loader size={20} className="animate-spin" />
                Confirming Appointment…
              </>
            ) : (
              <>
                <CheckCircle size={20} />
                Confirm Appointment
              </>
            )}
          </button>
        </div>
      )}

      {/* ── Navigation ── */}
      <div className="flex gap-3 mt-6">
        {step > 1 && (
          <button
            onClick={() => setStep(s => s - 1)}
            className="flex items-center gap-2 px-5 py-3 rounded-xl border-2 border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
          >
            <ChevronLeft size={16} /> Back
          </button>
        )}
        {step < TOTAL_STEPS && (
          <button
            onClick={() => { if (canProceed()) setStep(s => s + 1); }}
            disabled={!canProceed()}
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-white font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundColor: canProceed() ? '#1B6B45' : '#9CA3AF' }}
          >
            Continue <ArrowRight size={16} />
          </button>
        )}
      </div>

      {!canProceed() && step === 1 && (
        <p className="text-center text-xs text-gray-400 mt-2">Please select an institution and specialty to continue.</p>
      )}
      {!canProceed() && step === 2 && (
        <p className="text-center text-xs text-gray-400 mt-2">Please pick a date and time slot to continue.</p>
      )}
      {!canProceed() && step === 3 && (
        <p className="text-center text-xs text-gray-400 mt-2">Please provide a reason for your visit to continue.</p>
      )}
    </div>
  );
}

// ─── Confirmation Screen ────────────────────────────────────────────────────────

function ConfirmationScreen({ institution, specialty, date, slot, patient, onDone }: {
  institution: typeof INSTITUTIONS[0];
  specialty: Specialty;
  date: string;
  slot: string;
  patient: typeof PATIENTS[0];
  onDone: () => void;
}) {
  const d = new Date(date);
  const formattedDate = d.toLocaleDateString('en-SG', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  return (
    <div className="text-center">
      {/* Success animation */}
      <div className="w-20 h-20 rounded-full mx-auto mb-4 flex items-center justify-center shadow-lg" style={{ background: 'linear-gradient(135deg, #1B9A7A 0%, #1B6B45 100%)' }}>
        <CheckCircle size={36} className="text-white" />
      </div>
      <h2 className="text-xl font-bold text-gray-800 mb-1">Appointment Confirmed!</h2>
      <p className="text-gray-500 text-sm mb-6">A confirmation SMS will be sent to your registered mobile number.</p>

      {/* Booking card */}
      <div className="bg-white rounded-2xl shadow-md border border-gray-100 text-left overflow-hidden mb-5">
        <div className="h-2" style={{ backgroundColor: institution.color }} />
        <div className="p-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold" style={{ backgroundColor: institution.color }}>
              {institution.short}
            </div>
            <div>
              <p className="font-bold text-gray-800">{institution.name}</p>
              <p className="text-sm" style={{ color: institution.color }}>{specialty.name}</p>
            </div>
          </div>
          <div className="space-y-2 text-sm text-gray-600">
            <div className="flex items-center gap-2"><User size={14} style={{ color: '#1B6B45' }} /><span>{patient.name}</span></div>
            <div className="flex items-center gap-2"><Calendar size={14} style={{ color: '#1B6B45' }} /><span>{formattedDate}</span></div>
            <div className="flex items-center gap-2"><Clock size={14} style={{ color: '#1B6B45' }} /><span>{slot}</span></div>
            <div className="flex items-center gap-2"><MapPin size={14} style={{ color: '#1B6B45' }} /><span>{institution.address}</span></div>
          </div>
          <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
            <span className="text-xs text-gray-400">Ref: HH-{Math.random().toString(36).substring(2, 9).toUpperCase()}</span>
            <span className="text-xs font-medium text-green-700 bg-green-50 px-2.5 py-1 rounded-full flex items-center gap-1">
              <CheckCircle size={11} /> Confirmed
            </span>
          </div>
        </div>
      </div>

      {specialty.prepNote && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-5 text-left flex items-start gap-2">
          <AlertCircle size={15} className="text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-amber-800"><strong>Reminder:</strong> {specialty.prepNote}</p>
        </div>
      )}

      <button
        onClick={onDone}
        className="w-full py-4 rounded-2xl text-white font-semibold"
        style={{ backgroundColor: '#1B6B45' }}
      >
        View My Appointments
      </button>
    </div>
  );
}

// ─── Sub-components ────────────────────────────────────────────────────────────

function StepProgress({ current, total, labels }: { current: number; total: number; labels: string[] }) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-0 mb-3">
        {Array.from({ length: total }).map((_, i) => {
          const stepNum = i + 1;
          const done = stepNum < current;
          const active = stepNum === current;
          return (
            <div key={i} className="flex items-center flex-1 last:flex-none">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 transition-all"
                style={
                  done ? { backgroundColor: '#1B6B45', color: 'white' }
                  : active ? { backgroundColor: '#1B6B45', color: 'white', boxShadow: '0 0 0 3px #E8F5EE' }
                  : { backgroundColor: '#F3F4F6', color: '#9CA3AF' }
                }
              >
                {done ? <CheckCircle size={14} /> : stepNum}
              </div>
              {i < total - 1 && (
                <div className="flex-1 h-0.5 mx-1 rounded-full transition-all" style={{ backgroundColor: done ? '#1B6B45' : '#E5E7EB' }} />
              )}
            </div>
          );
        })}
      </div>
      <div className="flex justify-between">
        {labels.map((l, i) => (
          <span key={l} className="text-xs transition-all" style={{ color: i + 1 <= current ? '#1B6B45' : '#9CA3AF', fontWeight: i + 1 === current ? 700 : 400 }}>
            {l}
          </span>
        ))}
      </div>
    </div>
  );
}

function SlotButton({ slot, selected, taken, onClick }: { slot: string; selected: boolean; taken?: boolean; onClick: () => void }) {
  if (taken) {
    return (
      <button disabled className="px-2 py-2.5 rounded-xl text-xs border-2 border-dashed border-gray-200 text-gray-300 cursor-not-allowed line-through">
        {slot}
      </button>
    );
  }
  return (
    <button
      onClick={onClick}
      className="px-2 py-2.5 rounded-xl text-xs border-2 font-medium transition-all"
      style={selected ? { borderColor: '#1B6B45', backgroundColor: '#1B6B45', color: 'white' } : { borderColor: '#E5E7EB', backgroundColor: 'white', color: '#374151' }}
    >
      {slot}
    </button>
  );
}

function ReviewRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3 px-5 py-3.5">
      <div className="mt-0.5 flex-shrink-0">{icon}</div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-sm font-medium text-gray-800 mt-0.5">{value}</p>
      </div>
    </div>
  );
}
