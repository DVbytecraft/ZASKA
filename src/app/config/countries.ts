export interface SupportedCountry {
  code: string;
  name: string;
  flag: string;
  dialCode: string;
  currency: string;
  language: "fr" | "en";
  mobileMoneyEnabled: boolean;
}

export interface MobileMoneyOperator {
  id: string;
  name: string;
  color: string;
}

export const SUPPORTED_COUNTRIES: SupportedCountry[] = [
  { code: 'TG', name: 'Togo',          flag: '🇹🇬', dialCode: '+228', currency: 'XOF', language: 'fr', mobileMoneyEnabled: true  },
  { code: 'CI', name: "Côte d'Ivoire", flag: '🇨🇮', dialCode: '+225', currency: 'XOF', language: 'fr', mobileMoneyEnabled: true  },
  { code: 'SN', name: 'Sénégal',       flag: '🇸🇳', dialCode: '+221', currency: 'XOF', language: 'fr', mobileMoneyEnabled: true  },
  { code: 'BJ', name: 'Bénin',         flag: '🇧🇯', dialCode: '+229', currency: 'XOF', language: 'fr', mobileMoneyEnabled: true  },
  { code: 'BF', name: 'Burkina Faso',  flag: '🇧🇫', dialCode: '+226', currency: 'XOF', language: 'fr', mobileMoneyEnabled: true  },
  { code: 'ML', name: 'Mali',          flag: '🇲🇱', dialCode: '+223', currency: 'XOF', language: 'fr', mobileMoneyEnabled: true  },
  { code: 'NE', name: 'Niger',         flag: '🇳🇪', dialCode: '+227', currency: 'XOF', language: 'fr', mobileMoneyEnabled: true  },
  { code: 'CM', name: 'Cameroun',      flag: '🇨🇲', dialCode: '+237', currency: 'XAF', language: 'fr', mobileMoneyEnabled: true  },
  { code: 'GH', name: 'Ghana',         flag: '🇬🇭', dialCode: '+233', currency: 'GHS', language: 'en', mobileMoneyEnabled: true  },
  { code: 'NG', name: 'Nigeria',       flag: '🇳🇬', dialCode: '+234', currency: 'NGN', language: 'en', mobileMoneyEnabled: true  },
  { code: 'KE', name: 'Kenya',         flag: '🇰🇪', dialCode: '+254', currency: 'KES', language: 'en', mobileMoneyEnabled: true  },
  { code: 'FR', name: 'France',        flag: '🇫🇷', dialCode: '+33',  currency: 'EUR', language: 'fr', mobileMoneyEnabled: false },
  { code: 'BE', name: 'Belgique',      flag: '🇧🇪', dialCode: '+32',  currency: 'EUR', language: 'fr', mobileMoneyEnabled: false },
  { code: 'US', name: 'United States', flag: '🇺🇸', dialCode: '+1',   currency: 'USD', language: 'en', mobileMoneyEnabled: false },
];

export const MOBILE_MONEY_OPERATORS: Record<string, MobileMoneyOperator[]> = {
  TG: [
    { id: 'tmoney',       name: 'T-Money',        color: '#FF6B00' },
    { id: 'flooz',        name: 'Flooz',           color: '#0066CC' },
  ],
  CI: [
    { id: 'orange_money', name: 'Orange Money',    color: '#FF6600' },
    { id: 'wave',         name: 'Wave',            color: '#1B75BC' },
    { id: 'mtn_momo',     name: 'MTN MoMo',        color: '#FFC107' },
    { id: 'moov_money',   name: 'Moov Money',      color: '#00A0E3' },
  ],
  SN: [
    { id: 'orange_money', name: 'Orange Money',    color: '#FF6600' },
    { id: 'wave',         name: 'Wave',            color: '#1B75BC' },
    { id: 'free_money',   name: 'Free Money',      color: '#E40000' },
  ],
  BJ: [
    { id: 'mtn_momo',     name: 'MTN MoMo',        color: '#FFC107' },
    { id: 'moov_money',   name: 'Moov Money',      color: '#00A0E3' },
  ],
  BF: [
    { id: 'orange_money', name: 'Orange Money',    color: '#FF6600' },
    { id: 'moov_money',   name: 'Moov Money',      color: '#00A0E3' },
  ],
  ML: [
    { id: 'orange_money', name: 'Orange Money',    color: '#FF6600' },
    { id: 'moov_money',   name: 'Moov Money',      color: '#00A0E3' },
  ],
  NE: [
    { id: 'orange_money', name: 'Orange Money',    color: '#FF6600' },
    { id: 'moov_money',   name: 'Moov Money',      color: '#00A0E3' },
  ],
  CM: [
    { id: 'orange_money', name: 'Orange Money',    color: '#FF6600' },
    { id: 'mtn_momo',     name: 'MTN MoMo',        color: '#FFC107' },
  ],
  GH: [
    { id: 'mtn_momo',     name: 'MTN MoMo',        color: '#FFC107' },
    { id: 'airteltigo',   name: 'AirtelTigo Money', color: '#E40000' },
    { id: 'vodafone_cash',name: 'Vodafone Cash',   color: '#E60000' },
  ],
  NG: [
    { id: 'mtn_momo',     name: 'MTN MoMo',        color: '#FFC107' },
    { id: 'airtel_money', name: 'Airtel Money',     color: '#E40000' },
  ],
  KE: [
    { id: 'mpesa',        name: 'M-Pesa',          color: '#4CAF50' },
    { id: 'airtel_money', name: 'Airtel Money',     color: '#E40000' },
  ],
};

export function getCountry(code: string): SupportedCountry | undefined {
  return SUPPORTED_COUNTRIES.find(c => c.code === code.toUpperCase());
}

export function getOperators(countryCode: string): MobileMoneyOperator[] {
  return MOBILE_MONEY_OPERATORS[countryCode.toUpperCase()] ?? [];
}
