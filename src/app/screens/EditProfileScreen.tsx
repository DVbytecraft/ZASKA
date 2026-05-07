import { useEffect, useState } from 'react';
import { ArrowLeft, Camera, User, Mail, Phone, Loader2 } from 'lucide-react';
import { Button } from '../components/Button';
import { Avatar } from '../components/Avatar';
import { userService } from '@zaska/shared-services';

interface EditProfileScreenProps {
  onBack: () => void;
  onSave: () => void;
}

export function EditProfileScreen({ onBack, onSave }: EditProfileScreenProps) {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    userService.getMe()
      .then((profile) => {
        setFirstName(profile.first_name ?? '');
        setLastName(profile.last_name ?? '');
        setEmail(profile.email ?? '');
        setPhone(profile.phone ?? '');
      })
      .catch(() => setError('Impossible de charger le profil'))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await userService.updateProfile({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      });
      onSave();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  };

  const displayName = [firstName, lastName].filter(Boolean).join(' ') || 'Profil';

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-xl font-semibold text-gray-900">Edit Profile</h2>
          <div className="w-10" />
        </div>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 size={32} className="animate-spin text-[#6D28D9]" />
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-auto p-6">
            <div className="flex flex-col items-center mb-8">
              <div className="relative">
                <Avatar name={displayName} size="xl" />
                <button className="absolute bottom-0 right-0 w-10 h-10 bg-[#6D28D9] rounded-full flex items-center justify-center shadow-lg hover:bg-[#5B21B6] transition-colors">
                  <Camera size={18} className="text-white" />
                </button>
              </div>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Prénom</label>
                  <div className="relative">
                    <User size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                      type="text"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#6D28D9] focus:border-transparent"
                      placeholder="Prénom"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Nom</label>
                  <input
                    type="text"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#6D28D9] focus:border-transparent"
                    placeholder="Nom"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
                <div className="relative">
                  <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="email"
                    value={email}
                    readOnly
                    className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl bg-gray-50 text-gray-500 cursor-not-allowed"
                  />
                </div>
                <p className="text-xs text-gray-400 mt-1">L'email ne peut pas être modifié.</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Téléphone</label>
                <div className="relative">
                  <Phone size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="tel"
                    value={phone}
                    readOnly
                    className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl bg-gray-50 text-gray-500 cursor-not-allowed"
                  />
                </div>
                <p className="text-xs text-gray-400 mt-1">Le téléphone ne peut pas être modifié.</p>
              </div>
            </div>

            {error && (
              <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2 mt-4">{error}</p>
            )}
          </div>

          <div className="p-6 border-t border-gray-200">
            <Button fullWidth onClick={handleSave} disabled={saving}>
              {saving ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 size={16} className="animate-spin" /> Sauvegarde...
                </span>
              ) : 'Enregistrer'}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
