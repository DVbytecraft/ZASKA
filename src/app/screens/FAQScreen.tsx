import { useState } from 'react';
import { ArrowLeft, ChevronDown } from 'lucide-react';

interface FAQScreenProps {
  onBack: () => void;
}

export function FAQScreen({ onBack }: FAQScreenProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const faqs = [
    { q: 'How does ZASKA work?', a: 'ZASKA connects you with nearby taskers who can help with everyday tasks. Simply post your task, get matched, and get it done.' },
    { q: 'How do I pay?', a: 'We accept mobile money, cards, and wallet payments. Your payment is held securely in escrow until the task is completed.' },
    { q: 'What if I\'m not satisfied?', a: 'Contact support within 24 hours and we\'ll help resolve the issue or provide a refund.' },
    { q: 'How do I become a tasker?', a: 'Switch to tasker mode in your profile, complete verification, and start accepting tasks.' },
    { q: 'Is my payment secure?', a: 'Yes, all payments are encrypted and held in escrow until you confirm task completion.' }
  ];

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">FAQ</h2>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-3">
        {faqs.map((faq, index) => (
          <div key={index} className="border border-gray-200 rounded-xl overflow-hidden">
            <button
              onClick={() => setOpenIndex(openIndex === index ? null : index)}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
            >
              <span className="font-semibold text-gray-900 text-left">{faq.q}</span>
              <ChevronDown
                size={20}
                className={`text-gray-600 transition-transform ${openIndex === index ? 'rotate-180' : ''}`}
              />
            </button>
            {openIndex === index && (
              <div className="px-4 pb-4 text-gray-600 text-sm">
                {faq.a}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
