import React from 'react';
import { CONTACT_INFO } from '../constants';

export const Footer: React.FC = () => {
  return (
    <footer className="bg-[#0b1f1a] border-t border-brand-medium/30 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center gap-6">
        
        <div className="text-center md:text-left">
           <div className="flex items-center justify-center md:justify-start gap-2 mb-2">
                <span className="font-serif text-2xl font-bold text-brand-copper">LF</span>
                <span className="text-sm text-gray-400 uppercase tracking-widest">LoanFlow Processing LLC</span>
           </div>
           <p className="text-gray-500 text-xs">
             &copy; {new Date().getFullYear()} LoanFlow Processing LLC. All rights reserved.
           </p>
        </div>

        <div className="flex gap-8 text-sm text-gray-400">
           <a href="#" className="hover:text-brand-copper transition-colors">Privacy Policy</a>
           <a href="#" className="hover:text-brand-copper transition-colors">Terms of Service</a>
           <a href={`mailto:${CONTACT_INFO.email}`} className="hover:text-brand-copper transition-colors">Contact Support</a>
        </div>

      </div>
    </footer>
  );
};