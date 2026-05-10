import { useRef, useState, useEffect } from 'react';
import { Camera, X, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';

interface AIFlags {
  suspicious: boolean;
  confidence: 'low' | 'medium' | 'high';
  reasons: string[];
}

async function analyzePhoto(file: File): Promise<AIFlags> {
  const reasons: string[] = [];

  if (/generated|ai[-_ ]|dalle|midjourney|stable[_\-]?diff|sora|flux|firefly|gpt|bing.image/i.test(file.name)) {
    reasons.push('Nom de fichier suspect');
  }

  if (file.type === 'image/png') {
    reasons.push('Format PNG (typique des images générées par IA)');
  }

  if (file.type === 'image/jpeg' || file.type === 'image/jpg') {
    try {
      const buf = await file.slice(0, 131072).arrayBuffer();
      const view = new DataView(buf);
      let hasExif = false;

      if (view.getUint8(0) === 0xff && view.getUint8(1) === 0xd8) {
        let off = 2;
        while (off < buf.byteLength - 8) {
          if (view.getUint8(off) !== 0xff) break;
          const marker = view.getUint8(off + 1);
          if (marker === 0xe1) {
            // Check for 'Exif\0\0' signature
            const sig = [0x45, 0x78, 0x69, 0x66, 0x00, 0x00];
            if (
              off + 10 < buf.byteLength &&
              sig.every((b, i) => view.getUint8(off + 4 + i) === b)
            ) {
              hasExif = true;
            }
            break;
          }
          if (marker === 0xda || marker === 0xd9) break;
          if (off + 3 >= buf.byteLength) break;
          const segLen = view.getUint16(off + 2);
          if (segLen < 2) break;
          off += 2 + segLen;
        }
      }

      if (!hasExif) reasons.push('Aucune métadonnée de caméra (EXIF manquant)');
    } catch {
      // Skip EXIF check on read error
    }
  }

  const dims = await new Promise<{ w: number; h: number } | null>((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve({ w: img.naturalWidth, h: img.naturalHeight });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(null);
    };
    img.src = url;
  });

  if (dims) {
    const isExactSquare = dims.w === dims.h;
    const commonAISizes = [512, 768, 1024, 1152, 1280, 1344, 1536, 2048];
    if (isExactSquare && commonAISizes.includes(dims.w)) {
      reasons.push(`Dimensions typiques IA (${dims.w}×${dims.h})`);
    }
  }

  const score = reasons.length;
  return {
    suspicious: score > 0,
    confidence: score >= 2 ? 'high' : score === 1 ? 'medium' : 'low',
    reasons,
  };
}

interface ProofPhotoUploadProps {
  label: string;
  hint?: string;
  required?: boolean;
  onFileChange: (file: File | null) => void;
  className?: string;
}

export function ProofPhotoUpload({
  label,
  hint,
  required,
  onFileChange,
  className = '',
}: ProofPhotoUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [flags, setFlags] = useState<AIFlags | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  const handleFile = async (f: File) => {
    if (f.size > 10 * 1024 * 1024) {
      alert('Fichier trop grand. Maximum 10 Mo.');
      return;
    }
    if (preview) URL.revokeObjectURL(preview);
    const url = URL.createObjectURL(f);
    setFile(f);
    setPreview(url);
    setFlags(null);
    onFileChange(f);

    setChecking(true);
    try {
      const result = await analyzePhoto(f);
      setFlags(result);
    } finally {
      setChecking(false);
    }
  };

  const handleRemove = () => {
    if (preview) URL.revokeObjectURL(preview);
    setFile(null);
    setPreview(null);
    setFlags(null);
    onFileChange(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className={className}>
      <label className="block text-sm font-semibold text-gray-700 mb-1">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {hint && <p className="text-xs text-gray-400 mb-2">{hint}</p>}

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFile(f);
        }}
      />

      {!file ? (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="w-full py-8 border-2 border-dashed border-gray-200 rounded-2xl flex flex-col items-center gap-3 hover:border-[#6D28D9] hover:bg-purple-50/40 transition-all active:scale-[0.98]"
        >
          <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center">
            <Camera size={26} className="text-gray-400" />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-gray-700">Prendre ou importer une photo</p>
            <p className="text-xs text-gray-400 mt-0.5">JPEG, PNG, WebP · max 10 Mo</p>
          </div>
        </button>
      ) : (
        <div className="rounded-2xl border-2 border-gray-100 overflow-hidden">
          <div className="relative">
            <img src={preview!} alt="Preuve" className="w-full h-48 object-cover" />
            <button
              type="button"
              onClick={handleRemove}
              className="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/60 flex items-center justify-center hover:bg-black/80 transition-colors"
            >
              <X size={16} className="text-white" />
            </button>
          </div>

          <div className="px-3 py-2 bg-gray-50 border-t border-gray-100 min-h-[36px] flex items-center">
            {checking ? (
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <Loader2 size={13} className="animate-spin" />
                Analyse de la photo en cours…
              </div>
            ) : flags && flags.suspicious ? (
              <div
                className={`flex items-start gap-2 w-full rounded-lg px-2 py-1.5 ${
                  flags.confidence === 'high' ? 'bg-red-50' : 'bg-amber-50'
                }`}
              >
                <AlertTriangle
                  size={14}
                  className={`flex-shrink-0 mt-0.5 ${
                    flags.confidence === 'high' ? 'text-red-500' : 'text-amber-500'
                  }`}
                />
                <div>
                  <p
                    className={`text-xs font-semibold ${
                      flags.confidence === 'high' ? 'text-red-700' : 'text-amber-700'
                    }`}
                  >
                    ⚠️ Photo potentiellement générée par IA
                  </p>
                  <p className="text-[10px] text-gray-500 mt-0.5 leading-relaxed">
                    {flags.reasons.join(' · ')}
                  </p>
                </div>
              </div>
            ) : flags && !flags.suspicious ? (
              <div className="flex items-center gap-2 text-xs text-green-700">
                <CheckCircle2 size={13} className="text-green-500 flex-shrink-0" />
                Métadonnées caméra détectées — photo authentique
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
