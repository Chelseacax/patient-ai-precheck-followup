import { useState } from 'react';
import { Link } from 'react-router';
import {
  ChevronLeft, User, Phone, Mail, MapPin, Heart,
  Edit3, Save, X, ShieldCheck, ChevronRight,
  AlertCircle, Plus, Trash2, Camera, Bell, Globe, Lock,
} from 'lucide-react';

interface EmergencyContact {
  id: string;
  name: string;
  relation: string;
  phone: string;
}

const INITIAL_CONTACTS: EmergencyContact[] = [
  { id: '1', name: 'Tan Wei Ming', relation: 'Son', phone: '+65 9123 4567' },
  { id: '2', name: 'Tan Siew Lian', relation: 'Daughter', phone: '+65 9765 4321' },
];

interface PersonalInfo {
  fullName: string;
  nric: string;
  dob: string;
  gender: string;
  nationality: string;
  email: string;
  phone: string;
  address: string;
  bloodType: string;
  allergies: string;
}

const INITIAL_INFO: PersonalInfo = {
  fullName: 'Tan Ah Kow',
  nric: 'T1234930C',
  dob: '15 March 1952',
  gender: 'Male',
  nationality: 'Singapore Citizen',
  email: 'tan.ahkow@gmail.com',
  phone: '+65 8234 5678',
  address: '451 Clementi Ave 3, #08-12, Singapore 120451',
  bloodType: 'O+',
  allergies: 'Penicillin, Sulfonamides',
};

type EditSection = 'personal' | 'contact' | 'medical' | null;

export function ProfilePage() {
  const [info, setInfo] = useState<PersonalInfo>(INITIAL_INFO);
  const [editSection, setEditSection] = useState<EditSection>(null);
  const [draft, setDraft] = useState<PersonalInfo>(INITIAL_INFO);
  const [contacts, setContacts] = useState<EmergencyContact[]>(INITIAL_CONTACTS);
  const [editingContact, setEditingContact] = useState<string | null>(null);
  const [showAddContact, setShowAddContact] = useState(false);
  const [newContact, setNewContact] = useState<Omit<EmergencyContact, 'id'>>({ name: '', relation: '', phone: '' });
  const [saved, setSaved] = useState<EditSection>(null);

  const startEdit = (section: EditSection) => {
    setDraft({ ...info });
    setEditSection(section);
  };

  const saveEdit = () => {
    setInfo({ ...draft });
    setSaved(editSection);
    setEditSection(null);
    setTimeout(() => setSaved(null), 2000);
  };

  const cancelEdit = () => {
    setDraft({ ...info });
    setEditSection(null);
  };

  const addContact = () => {
    if (newContact.name && newContact.phone) {
      setContacts((prev) => [...prev, { ...newContact, id: Date.now().toString() }]);
      setNewContact({ name: '', relation: '', phone: '' });
      setShowAddContact(false);
    }
  };

  const removeContact = (id: string) => {
    setContacts((prev) => prev.filter((c) => c.id !== id));
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link
          to="/app"
          className="w-10 h-10 rounded-xl flex items-center justify-center hover:bg-gray-200 bg-white shadow-sm border border-gray-100"
        >
          <ChevronLeft size={20} className="text-gray-600" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-800">My Profile</h1>
          <p className="text-gray-500 text-sm">Manage your personal and health information</p>
        </div>
      </div>

      {/* Profile Hero Card */}
      <div
        className="rounded-2xl p-6 mb-5 text-white relative overflow-hidden"
        style={{ background: 'linear-gradient(135deg, #1B6B45 0%, #0F4229 100%)' }}
      >
        <div className="absolute top-0 right-0 w-40 h-40 rounded-full bg-white/5 -translate-y-12 translate-x-12" />
        <div className="flex items-center gap-5 relative z-10">
          {/* Avatar */}
          <div className="relative flex-shrink-0">
            <div className="w-20 h-20 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center border-2 border-white/40">
              <span className="text-3xl font-bold">T</span>
            </div>
            <button className="absolute -bottom-1 -right-1 w-7 h-7 bg-amber-400 rounded-full flex items-center justify-center border-2 border-white">
              <Camera size={12} className="text-white" />
            </button>
          </div>
          {/* Info */}
          <div className="flex-1">
            <h2 className="text-xl font-bold">{info.fullName}</h2>
            <p className="text-white/80 text-sm mt-0.5">NRIC: T**XX930C</p>
            <p className="text-white/70 text-xs mt-0.5">{info.dob} · {info.gender} · {info.bloodType}</p>
            <div className="flex items-center gap-1.5 mt-2">
              <ShieldCheck size={14} className="text-green-300" />
              <span className="text-xs text-green-200">Singpass Verified Identity</span>
            </div>
          </div>
          {/* Edit button */}
          <button
            onClick={() => startEdit('personal')}
            className="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center hover:bg-white/30 transition-colors flex-shrink-0"
          >
            <Edit3 size={16} className="text-white" />
          </button>
        </div>
      </div>

      {/* Save Success Toast */}
      {saved && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 bg-green-700 text-white px-5 py-3 rounded-xl shadow-lg z-50 flex items-center gap-2 text-sm font-medium">
          <ShieldCheck size={16} />
          Changes saved successfully
        </div>
      )}

      {/* Personal Information */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 mb-4 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#E8F5EE' }}>
              <User size={16} style={{ color: '#1B6B45' }} />
            </div>
            <h3 className="font-semibold text-gray-800">Personal Information</h3>
          </div>
          {editSection === 'personal' ? (
            <div className="flex gap-2">
              <button
                onClick={saveEdit}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-white text-sm font-medium"
                style={{ backgroundColor: '#1B6B45' }}
              >
                <Save size={14} /> Save
              </button>
              <button
                onClick={cancelEdit}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-gray-600 text-sm border border-gray-200 hover:bg-gray-50"
              >
                <X size={14} /> Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => startEdit('personal')}
              className="flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg hover:bg-green-50 transition-colors"
              style={{ color: '#1B6B45' }}
            >
              <Edit3 size={14} /> Edit
            </button>
          )}
        </div>

        <div className="p-5 space-y-4">
          {editSection === 'personal' ? (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FieldInput label="Full Name" value={draft.fullName} onChange={(v) => setDraft((d) => ({ ...d, fullName: v }))} />
                <FieldReadonly label="NRIC / FIN" value="T**XX930C" note="Linked via Singpass" />
                <FieldReadonly label="Date of Birth" value={draft.dob} note="Cannot be changed" />
                <FieldReadonly label="Gender" value={draft.gender} />
                <FieldReadonly label="Nationality" value={draft.nationality} />
                <FieldSelect
                  label="Blood Type"
                  value={draft.bloodType}
                  options={['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']}
                  onChange={(v) => setDraft((d) => ({ ...d, bloodType: v }))}
                />
              </div>
              <FieldInput
                label="Known Allergies"
                value={draft.allergies}
                onChange={(v) => setDraft((d) => ({ ...d, allergies: v }))}
                placeholder="E.g. Penicillin, seafood, latex"
              />
            </>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FieldDisplay label="Full Name" value={info.fullName} />
              <FieldDisplay label="NRIC / FIN" value="T**XX930C" />
              <FieldDisplay label="Date of Birth" value={info.dob} />
              <FieldDisplay label="Gender" value={info.gender} />
              <FieldDisplay label="Nationality" value={info.nationality} />
              <FieldDisplay label="Blood Type" value={info.bloodType} highlight />
              <div className="sm:col-span-2">
                <FieldDisplay label="Known Allergies" value={info.allergies} alert />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Contact Information */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 mb-4 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#EFF6FF' }}>
              <Phone size={16} className="text-blue-600" />
            </div>
            <h3 className="font-semibold text-gray-800">Contact Information</h3>
          </div>
          {editSection === 'contact' ? (
            <div className="flex gap-2">
              <button
                onClick={saveEdit}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-white text-sm font-medium"
                style={{ backgroundColor: '#1B6B45' }}
              >
                <Save size={14} /> Save
              </button>
              <button onClick={cancelEdit} className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-gray-600 text-sm border border-gray-200 hover:bg-gray-50">
                <X size={14} /> Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => startEdit('contact')}
              className="flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg hover:bg-green-50 transition-colors"
              style={{ color: '#1B6B45' }}
            >
              <Edit3 size={14} /> Edit
            </button>
          )}
        </div>

        <div className="p-5 space-y-4">
          {editSection === 'contact' ? (
            <>
              <FieldInput label="Mobile Number" value={draft.phone} onChange={(v) => setDraft((d) => ({ ...d, phone: v }))} type="tel" />
              <FieldInput label="Email Address" value={draft.email} onChange={(v) => setDraft((d) => ({ ...d, email: v }))} type="email" />
              <FieldInput label="Home Address" value={draft.address} onChange={(v) => setDraft((d) => ({ ...d, address: v }))} />
            </>
          ) : (
            <>
              <div className="flex items-center gap-3 py-1">
                <Phone size={16} className="text-gray-400 flex-shrink-0" />
                <div>
                  <p className="text-xs text-gray-500">Mobile Number</p>
                  <p className="font-medium text-gray-800">{info.phone}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 py-1 border-t border-gray-50">
                <Mail size={16} className="text-gray-400 flex-shrink-0" />
                <div>
                  <p className="text-xs text-gray-500">Email Address</p>
                  <p className="font-medium text-gray-800">{info.email}</p>
                </div>
              </div>
              <div className="flex items-start gap-3 py-1 border-t border-gray-50">
                <MapPin size={16} className="text-gray-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs text-gray-500">Home Address</p>
                  <p className="font-medium text-gray-800">{info.address}</p>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Emergency Contacts */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 mb-4 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#FEE2E2' }}>
              <Heart size={16} className="text-red-500" />
            </div>
            <h3 className="font-semibold text-gray-800">Emergency Contacts</h3>
          </div>
          <button
            onClick={() => setShowAddContact(true)}
            className="flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg hover:bg-green-50 transition-colors"
            style={{ color: '#1B6B45' }}
          >
            <Plus size={14} /> Add
          </button>
        </div>

        <div className="p-5 space-y-3">
          {contacts.map((contact) => (
            <div key={contact.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0"
                  style={{ backgroundColor: '#1B6B45' }}
                >
                  {contact.name.charAt(0)}
                </div>
                <div>
                  <p className="font-medium text-gray-800 text-sm">{contact.name}</p>
                  <p className="text-xs text-gray-500">{contact.relation} · {contact.phone}</p>
                </div>
              </div>
              <button
                onClick={() => removeContact(contact.id)}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}

          {showAddContact && (
            <div className="border border-dashed border-green-300 rounded-xl p-4 bg-green-50">
              <p className="text-sm font-medium text-gray-700 mb-3">New Emergency Contact</p>
              <div className="space-y-2">
                <input
                  className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#1B6B45]"
                  placeholder="Full Name"
                  value={newContact.name}
                  onChange={(e) => setNewContact((n) => ({ ...n, name: e.target.value }))}
                />
                <input
                  className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#1B6B45]"
                  placeholder="Relationship (e.g. Son, Daughter)"
                  value={newContact.relation}
                  onChange={(e) => setNewContact((n) => ({ ...n, relation: e.target.value }))}
                />
                <input
                  className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#1B6B45]"
                  placeholder="Phone Number"
                  type="tel"
                  value={newContact.phone}
                  onChange={(e) => setNewContact((n) => ({ ...n, phone: e.target.value }))}
                />
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={addContact}
                    className="flex-1 py-2.5 rounded-lg text-white font-medium text-sm"
                    style={{ backgroundColor: '#1B6B45' }}
                  >
                    Add Contact
                  </button>
                  <button
                    onClick={() => { setShowAddContact(false); setNewContact({ name: '', relation: '', phone: '' }); }}
                    className="px-4 py-2.5 rounded-lg text-gray-600 border border-gray-200 text-sm hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          {contacts.length === 0 && !showAddContact && (
            <div className="text-center py-4 text-gray-400 text-sm">
              <Heart size={24} className="mx-auto mb-2 opacity-50" />
              No emergency contacts added yet.
            </div>
          )}
        </div>

        {/* Emergency tip */}
        <div className="mx-5 mb-5 flex items-start gap-2 bg-amber-50 border border-amber-100 rounded-xl p-3">
          <AlertCircle size={14} className="text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-700">
            Keep your emergency contacts up to date. In a medical emergency, healthcare providers may need to reach them.
          </p>
        </div>
      </div>

      {/* Settings & Preferences */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 mb-4 overflow-hidden">
        <div className="flex items-center gap-2 px-5 py-4 border-b border-gray-100">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#F5F3FF' }}>
            <Bell size={16} className="text-purple-600" />
          </div>
          <h3 className="font-semibold text-gray-800">Preferences & Accessibility</h3>
        </div>

        <div className="divide-y divide-gray-50">
          {[
            {
              icon: Bell,
              iconColor: '#7C3AED',
              iconBg: '#F5F3FF',
              label: 'Appointment Reminders',
              sub: 'SMS + Email notifications',
              toggle: true,
              defaultOn: true,
            },
            {
              icon: Globe,
              iconColor: '#1D4ED8',
              iconBg: '#EFF6FF',
              label: 'Language',
              sub: 'English',
              toggle: false,
              action: 'Change',
            },
            {
              icon: Lock,
              iconColor: '#DC2626',
              iconBg: '#FEE2E2',
              label: 'Privacy Settings',
              sub: 'Control data sharing',
              toggle: false,
              action: 'Manage',
            },
          ].map((item, i) => {
            const Icon = item.icon;
            return (
              <div key={i} className="flex items-center gap-3 px-5 py-4">
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: item.iconBg }}
                >
                  <Icon size={16} style={{ color: item.iconColor }} />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-800">{item.label}</p>
                  <p className="text-xs text-gray-500">{item.sub}</p>
                </div>
                {item.toggle ? (
                  <ToggleSwitch defaultOn={item.defaultOn} />
                ) : (
                  <button className="flex items-center gap-1 text-sm font-medium" style={{ color: '#1B6B45' }}>
                    {item.action}
                    <ChevronRight size={14} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Large Text Tip for Seniors */}
      <div className="bg-blue-50 border border-blue-100 rounded-2xl p-5 mb-4">
        <p className="text-sm font-semibold text-blue-800 mb-1">💡 Senior-Friendly Tip</p>
        <p className="text-sm text-blue-700">
          You can increase text size in your phone's Settings → Accessibility → Display &amp; Text Size to make HealthHub easier to read.
        </p>
      </div>

      {/* Account Actions */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="divide-y divide-gray-50">
          <button className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors">
            <div className="flex items-center gap-3">
              <ShieldCheck size={18} className="text-gray-400" />
              <span className="text-sm text-gray-700">Singpass Account Settings</span>
            </div>
            <ChevronRight size={16} className="text-gray-400" />
          </button>
          <Link
            to="/"
            className="w-full flex items-center justify-between px-5 py-4 hover:bg-red-50 transition-colors group block"
          >
            <div className="flex items-center gap-3">
              <X size={18} className="text-gray-400 group-hover:text-red-500" />
              <span className="text-sm text-gray-700 group-hover:text-red-600">Log Out of HealthHub</span>
            </div>
            <ChevronRight size={16} className="text-gray-400" />
          </Link>
        </div>
      </div>

      <p className="text-center text-xs text-gray-400 mt-6 mb-2">
        HealthHub v3.2.1 · Ministry of Health Singapore · © 2026
      </p>
    </div>
  );
}

// ── Helper sub-components ──────────────────────────────────────────────

function FieldDisplay({ label, value, highlight, alert }: { label: string; value: string; highlight?: boolean; alert?: boolean }) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p
        className={`text-sm font-medium ${
          highlight
            ? 'text-[#1B6B45]'
            : alert
            ? 'text-red-700 bg-red-50 px-2 py-0.5 rounded-lg inline-block'
            : 'text-gray-800'
        }`}
      >
        {value || '—'}
      </p>
    </div>
  );
}

function FieldReadonly({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <div className="px-3 py-2.5 bg-gray-50 border border-gray-100 rounded-lg text-sm text-gray-600">
        {value}
        {note && <span className="text-xs text-gray-400 ml-2">({note})</span>}
      </div>
    </div>
  );
}

function FieldInput({
  label, value, onChange, type = 'text', placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      <input
        type={type}
        className="w-full px-3 py-2.5 bg-white border-2 border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#1B6B45] transition-colors"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}

function FieldSelect({
  label, value, options, onChange,
}: {
  label: string; value: string; options: string[]; onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      <select
        className="w-full px-3 py-2.5 bg-white border-2 border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#1B6B45] transition-colors"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </select>
    </div>
  );
}

function ToggleSwitch({ defaultOn }: { defaultOn?: boolean }) {
  const [on, setOn] = useState(defaultOn ?? false);
  return (
    <button
      onClick={() => setOn((v) => !v)}
      className="relative w-12 h-6 rounded-full transition-colors flex-shrink-0"
      style={{ backgroundColor: on ? '#1B6B45' : '#D1D5DB' }}
      aria-label="Toggle"
    >
      <span
        className="absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform"
        style={{ transform: on ? 'translateX(26px)' : 'translateX(2px)' }}
      />
    </button>
  );
}
