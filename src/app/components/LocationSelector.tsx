import { useState } from 'react';
import { MapPin, X } from 'lucide-react';
import { Button } from './Button';

interface LocationSelectorProps {
  primaryLocation: string;
  additionalZones: string[];
  onPrimaryChange: (location: string) => void;
  onZonesChange: (zones: string[]) => void;
}

export function LocationSelector({
  primaryLocation,
  additionalZones,
  onPrimaryChange,
  onZonesChange
}: LocationSelectorProps) {
  const [showZoneInput, setShowZoneInput] = useState(false);
  const [newZone, setNewZone] = useState('');

  const addZone = () => {
    if (newZone.trim() && additionalZones.length < 2) {
      onZonesChange([...additionalZones, newZone.trim()]);
      setNewZone('');
      setShowZoneInput(false);
    }
  };

  const removeZone = (index: number) => {
    onZonesChange(additionalZones.filter((_, i) => i !== index));
  };

  return (
    <div>
      <div className="bg-gradient-to-br from-gray-50 to-gray-100 border-2 border-gray-200 rounded-2xl h-48 flex items-center justify-center mb-4 relative overflow-hidden">
        <div className="absolute inset-0 opacity-5">
          <div className="absolute inset-0" style={{
            backgroundImage: 'repeating-linear-gradient(0deg, #6D28D9 0px, #6D28D9 1px, transparent 1px, transparent 20px), repeating-linear-gradient(90deg, #6D28D9 0px, #6D28D9 1px, transparent 1px, transparent 20px)'
          }}></div>
        </div>
        <div className="text-center relative z-10">
          <div className="w-16 h-16 bg-[#6D28D9] rounded-2xl flex items-center justify-center mx-auto mb-3 shadow-lg">
            <MapPin size={32} className="text-white" strokeWidth={2.5} />
          </div>
          <p className="font-semibold text-gray-900">{primaryLocation}</p>
          <p className="text-sm text-gray-500">Primary location</p>
        </div>
      </div>

      <button
        onClick={() => {}}
        className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl font-medium text-gray-900 hover:border-[#6D28D9] hover:text-[#6D28D9] hover:bg-[#6D28D9]/5 transition-all mb-4"
      >
        Change primary location
      </button>

      {additionalZones.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Additional zones</p>
          <div className="flex flex-wrap gap-2">
            {additionalZones.map((zone, index) => (
              <div key={index} className="inline-flex items-center gap-2 px-3 py-1.5 bg-[#6D28D9]/10 text-[#6D28D9] rounded-lg text-sm font-medium">
                <MapPin size={14} />
                <span>{zone}</span>
                <button onClick={() => removeZone(index)} className="hover:bg-[#6D28D9]/20 rounded p-0.5">
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {additionalZones.length < 2 && !showZoneInput && (
        <button
          onClick={() => setShowZoneInput(true)}
          className="text-[#6D28D9] font-medium text-sm hover:underline"
        >
          + Add nearby zone ({2 - additionalZones.length} remaining)
        </button>
      )}

      {showZoneInput && (
        <div className="flex gap-2">
          <input
            type="text"
            value={newZone}
            onChange={(e) => setNewZone(e.target.value)}
            placeholder="Enter zone name"
            className="flex-1 px-4 py-2.5 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm"
            onKeyPress={(e) => e.key === 'Enter' && addZone()}
          />
          <button onClick={addZone} className="px-4 py-2.5 bg-[#6D28D9] text-white rounded-xl font-medium text-sm">
            Add
          </button>
        </div>
      )}
    </div>
  );
}
