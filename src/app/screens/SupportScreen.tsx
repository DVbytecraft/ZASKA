import { Card } from '../components/Card';
import { ArrowLeft, Phone, MessageCircle, Mail, HelpCircle } from 'lucide-react';

interface SupportScreenProps {
  onBack: () => void;
  onFAQ: () => void;
}

export function SupportScreen({ onBack, onFAQ }: SupportScreenProps) {
  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">Support</h2>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-3">
        <Card onClick={onFAQ} className="hover:shadow-lg transition-all">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-purple-50 flex items-center justify-center">
              <HelpCircle size={24} className="text-[#6D28D9]" />
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-gray-900">FAQ</h4>
              <p className="text-sm text-gray-600">Find answers to common questions</p>
            </div>
          </div>
        </Card>

        <Card className="hover:shadow-lg transition-all">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center">
              <Phone size={24} className="text-blue-600" />
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-gray-900">Call us</h4>
              <p className="text-sm text-gray-600">+221 77 123 4567</p>
            </div>
          </div>
        </Card>

        <Card className="hover:shadow-lg transition-all">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-green-50 flex items-center justify-center">
              <MessageCircle size={24} className="text-green-600" />
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-gray-900">Chat with us</h4>
              <p className="text-sm text-gray-600">Average response time: 2 min</p>
            </div>
          </div>
        </Card>

        <Card className="hover:shadow-lg transition-all">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-orange-50 flex items-center justify-center">
              <Mail size={24} className="text-orange-600" />
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-gray-900">Email us</h4>
              <p className="text-sm text-gray-600">support@zaska.com</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
