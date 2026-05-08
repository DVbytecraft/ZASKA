import { useEffect, useRef, useState } from 'react';
import { apiClient } from '@zaska/shared-services';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { ArrowLeft, Camera, CheckCircle2, Clock, FileText, Upload, XCircle } from 'lucide-react';

interface KycScreenProps {
  onBack: () => void;
  onComplete: () => void;
}

type KycStatus = 'not_submitted' | 'pending' | 'approved' | 'rejected';

interface KycStatusData {
  status: KycStatus;
  reviewerNote?: string | null;
  reviewedAt?: string | null;
  createdAt?: string;
}

async function submitKyc(idFile: File, selfieFile: File): Promise<KycStatusData> {
  const token = apiClient.getAccessToken();
  if (!token) throw new Error('Not authenticated');
  const baseUrl: string = import.meta.env.VITE_API_URL || 'http://localhost:6969/api';
  const form = new FormData();
  form.append('id_document', idFile);
  form.append('selfie', selfieFile);
  const res = await fetch(`${baseUrl}/kyc/submit`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  const json = await res.json();
  if (!json.success) throw new Error(json.error ?? 'Failed to submit KYC');
  return json.data as KycStatusData;
}

function StatusBadge({ status }: { status: KycStatus }) {
  if (status === 'approved') {
    return (
      <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
        <CheckCircle2 size={20} className="text-green-600 flex-shrink-0" />
        <div>
          <p className="font-semibold text-green-800 text-sm">Identity verified</p>
          <p className="text-xs text-green-600">Your account is fully verified</p>
        </div>
      </div>
    );
  }
  if (status === 'pending') {
    return (
      <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
        <Clock size={20} className="text-amber-600 flex-shrink-0" />
        <div>
          <p className="font-semibold text-amber-800 text-sm">Under review</p>
          <p className="text-xs text-amber-600">We'll notify you within 24h</p>
        </div>
      </div>
    );
  }
  if (status === 'rejected') {
    return (
      <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
        <XCircle size={20} className="text-red-600 flex-shrink-0" />
        <div>
          <p className="font-semibold text-red-800 text-sm">Verification rejected</p>
          <p className="text-xs text-red-600">Please resubmit with clearer documents</p>
        </div>
      </div>
    );
  }
  return null;
}

export function KycScreen({ onBack, onComplete }: KycScreenProps) {
  const [kycStatus, setKycStatus] = useState<KycStatusData | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [idFile, setIdFile] = useState<File | null>(null);
  const [selfieFile, setSelfieFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const idRef = useRef<HTMLInputElement>(null);
  const selfieRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    apiClient.get<KycStatusData>('/kyc/status')
      .then(setKycStatus)
      .catch(() => setKycStatus({ status: 'not_submitted' }))
      .finally(() => setLoadingStatus(false));
  }, []);

  const handleSubmit = async () => {
    if (!idFile || !selfieFile) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await submitKyc(idFile, selfieFile);
      setKycStatus(result);
      if (result.status === 'approved') {
        onComplete();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la soumission');
    } finally {
      setSubmitting(false);
    }
  };

  const alreadySubmitted = kycStatus && kycStatus.status !== 'not_submitted' && kycStatus.status !== 'rejected';

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Identity verification</h2>
            <p className="text-sm text-gray-500">Required to send and receive payments</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6 space-y-4">
        {loadingStatus ? (
          <div className="h-16 bg-gray-200 rounded-2xl animate-pulse" />
        ) : (
          kycStatus && kycStatus.status !== 'not_submitted' && (
            <StatusBadge status={kycStatus.status} />
          )
        )}

        {kycStatus?.reviewerNote && (
          <Card className="bg-red-50 border-red-100">
            <p className="text-sm text-red-700 font-medium">Reason: {kycStatus.reviewerNote}</p>
          </Card>
        )}

        {!alreadySubmitted && (
          <>
            <Card>
              <h3 className="font-semibold text-gray-900 mb-4">What you need to provide</h3>
              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-xl bg-purple-50 flex items-center justify-center flex-shrink-0">
                    <FileText size={18} className="text-[#6D28D9]" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 text-sm">Government-issued ID</p>
                    <p className="text-xs text-gray-500">National ID card, passport, or driver's license</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-xl bg-purple-50 flex items-center justify-center flex-shrink-0">
                    <Camera size={18} className="text-[#6D28D9]" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 text-sm">Selfie with your ID</p>
                    <p className="text-xs text-gray-500">Hold your document next to your face</p>
                  </div>
                </div>
              </div>
            </Card>

            {/* ID Document upload */}
            <div>
              <p className="text-sm font-semibold text-gray-700 mb-2">ID Document</p>
              <input
                ref={idRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => setIdFile(e.target.files?.[0] ?? null)}
              />
              <button
                onClick={() => idRef.current?.click()}
                className={`w-full border-2 border-dashed rounded-2xl p-6 flex flex-col items-center gap-2 transition-all ${
                  idFile
                    ? 'border-[#6D28D9] bg-[#6D28D9]/5'
                    : 'border-gray-300 hover:border-gray-400 bg-white'
                }`}
              >
                {idFile ? (
                  <>
                    <CheckCircle2 size={28} className="text-[#6D28D9]" />
                    <p className="text-sm font-medium text-[#6D28D9]">{idFile.name}</p>
                    <p className="text-xs text-gray-500">Tap to change</p>
                  </>
                ) : (
                  <>
                    <Upload size={28} className="text-gray-400" />
                    <p className="text-sm font-medium text-gray-700">Upload ID document</p>
                    <p className="text-xs text-gray-500">JPEG, PNG or WebP · Max 10 MB</p>
                  </>
                )}
              </button>
            </div>

            {/* Selfie upload */}
            <div>
              <p className="text-sm font-semibold text-gray-700 mb-2">Selfie with ID</p>
              <input
                ref={selfieRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => setSelfieFile(e.target.files?.[0] ?? null)}
              />
              <button
                onClick={() => selfieRef.current?.click()}
                className={`w-full border-2 border-dashed rounded-2xl p-6 flex flex-col items-center gap-2 transition-all ${
                  selfieFile
                    ? 'border-[#6D28D9] bg-[#6D28D9]/5'
                    : 'border-gray-300 hover:border-gray-400 bg-white'
                }`}
              >
                {selfieFile ? (
                  <>
                    <CheckCircle2 size={28} className="text-[#6D28D9]" />
                    <p className="text-sm font-medium text-[#6D28D9]">{selfieFile.name}</p>
                    <p className="text-xs text-gray-500">Tap to change</p>
                  </>
                ) : (
                  <>
                    <Camera size={28} className="text-gray-400" />
                    <p className="text-sm font-medium text-gray-700">Take or upload selfie</p>
                    <p className="text-xs text-gray-500">Hold your ID next to your face</p>
                  </>
                )}
              </button>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-100 rounded-xl p-3">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}
          </>
        )}

        {alreadySubmitted && kycStatus?.status === 'approved' && (
          <Card>
            <p className="text-sm text-gray-600 text-center py-4">
              Your identity is verified. You can now make and receive payments.
            </p>
          </Card>
        )}
      </div>

      {!alreadySubmitted && (
        <div className="px-6 py-4 bg-white border-t border-gray-200">
          <Button
            fullWidth
            onClick={handleSubmit}
            disabled={!idFile || !selfieFile || submitting}
          >
            {submitting ? 'Envoi en cours…' : 'Soumettre pour vérification'}
          </Button>
        </div>
      )}
    </div>
  );
}
