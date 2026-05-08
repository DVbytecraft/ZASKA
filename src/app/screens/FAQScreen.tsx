import { useState } from 'react';
import { ArrowLeft, ChevronDown } from 'lucide-react';

interface FAQScreenProps {
  onBack: () => void;
}

export function FAQScreen({ onBack }: FAQScreenProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const faqs = [
    { q: 'Comment fonctionne ZASKA ?', a: 'ZASKA vous met en relation avec des prestataires proches de vous qui peuvent vous aider dans vos tâches quotidiennes. Publiez simplement votre tâche, trouvez un match, et c\'est fait.' },
    { q: 'Comment payer ?', a: 'Nous acceptons le mobile money, les cartes et les paiements par portefeuille. Votre paiement est conservé en toute sécurité en séquestre jusqu\'à la réalisation de la tâche.' },
    { q: 'Et si je ne suis pas satisfait ?', a: 'Contactez le support dans les 24 heures et nous vous aiderons à résoudre le problème ou vous rembourserons.' },
    { q: 'Comment devenir prestataire ?', a: 'Passez en mode prestataire dans votre profil, complétez la vérification et commencez à accepter des tâches.' },
    { q: 'Mon paiement est-il sécurisé ?', a: 'Oui, tous les paiements sont chiffrés et conservés en séquestre jusqu\'à ce que vous confirmiez la réalisation de la tâche.' },
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
