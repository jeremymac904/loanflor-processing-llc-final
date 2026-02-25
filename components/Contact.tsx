import React from 'react';
import { Mail, Phone, MapPin, Send } from 'lucide-react';
import { CONTACT_INFO } from '../constants';

export const Contact: React.FC = () => {
  return (
    <section id="contact" className="py-24 bg-brand-dark relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-brand-copper/5 rounded-full blur-[100px] pointer-events-none"></div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">
          
          <div>
            <span className="text-brand-copper uppercase tracking-[0.2em] text-xs font-bold">Contact Us</span>
            <h2 className="mt-3 text-4xl md:text-5xl font-serif font-bold bg-gradient-to-b from-white via-white/80 to-white/50 bg-clip-text text-transparent mb-8">Optimize Your Pipeline</h2>
            <p className="text-gray-400 text-lg mb-12 font-light">
              Contact Ashley directly to discuss onboarding and how LoanFlow can support your brokerage.
            </p>

            <div className="space-y-8">
              <div className="flex items-start gap-6 group">
                <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-brand-copper group-hover:bg-brand-copper group-hover:text-brand-dark transition-all">
                  <Phone size={20} />
                </div>
                <div>
                  <h4 className="text-white font-medium text-lg">Phone</h4>
                  <a href={`tel:${CONTACT_INFO.phone.replace(/[^0-9]/g, '')}`} className="text-gray-400 hover:text-brand-copper transition-colors">{CONTACT_INFO.phone}</a>
                </div>
              </div>

              <div className="flex items-start gap-6 group">
                <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-brand-copper group-hover:bg-brand-copper group-hover:text-brand-dark transition-all">
                  <Mail size={20} />
                </div>
                <div>
                  <h4 className="text-white font-medium text-lg">Email</h4>
                  <a href={`mailto:${CONTACT_INFO.email}`} className="text-gray-400 hover:text-brand-copper transition-colors">{CONTACT_INFO.email}</a>
                </div>
              </div>

              <div className="flex items-start gap-6 group">
                <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-brand-copper group-hover:bg-brand-copper group-hover:text-brand-dark transition-all">
                  <MapPin size={20} />
                </div>
                <div>
                  <h4 className="text-white font-medium text-lg">Service Area</h4>
                  <p className="text-gray-400">Serving Florida Brokers</p>
                  <p className="text-xs text-brand-copper/80 mt-1 uppercase tracking-wider font-bold">More states coming soon</p>
                </div>
              </div>
            </div>
          </div>

          <div className="relative rounded-2xl p-8 md:p-10 backdrop-blur-xl bg-white/[0.04] border border-white/10 shadow-[0_1px_0_rgba(255,255,255,0.10),0_22px_70px_rgba(0,0,0,0.60)] ring-1 ring-white/10">
            {/* Inner Depth Overlay */}
            <div className="absolute inset-0 rounded-2xl bg-gradient-to-b from-white/10 via-white/5 to-transparent opacity-60 pointer-events-none"></div>

            {/* Chrome Edge Highlight */}
            <div className="absolute inset-0 rounded-2xl pointer-events-none bg-[linear-gradient(135deg,rgba(255,255,255,0.18),rgba(255,255,255,0.04),rgba(255,255,255,0.14))] opacity-70 mix-blend-overlay"></div>

            <div className="relative z-10">
                <h3 className="text-2xl font-serif text-white mb-6">Send a Message</h3>
                <form className="space-y-5" onSubmit={(e) => e.preventDefault()}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div>
                    <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">First Name</label>
                    <input type="text" className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-copper/50 focus:bg-white/[0.02] transition-all" />
                    </div>
                    <div>
                    <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Last Name</label>
                    <input type="text" className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-copper/50 focus:bg-white/[0.02] transition-all" />
                    </div>
                </div>
                <div>
                    <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Email Address</label>
                    <input type="email" className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-copper/50 focus:bg-white/[0.02] transition-all" />
                </div>
                <div>
                    <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Message</label>
                    <textarea rows={4} className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-copper/50 focus:bg-white/[0.02] transition-all"></textarea>
                </div>
                {/* Copper Metallic Button (Primary) */}
                <button className="w-full relative inline-flex items-center justify-center gap-2 rounded-xl px-6 py-3 font-medium bg-gradient-to-b from-[#caa35a] via-[#b8893f] to-[#8f6a2f] shadow-[0_1px_0_rgba(255,255,255,0.18),0_20px_55px_rgba(0,0,0,0.60)] text-black/90 transition duration-300 hover:brightness-110 active:brightness-95">
                    {/* Specular highlight overlay */}
                    <span className="absolute inset-0 rounded-xl pointer-events-none bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.55),rgba(255,255,255,0)_55%)] opacity-60"></span>
                    
                    <span className="relative z-10 flex items-center gap-2">
                        Send Message <Send size={16} />
                    </span>
                </button>
                </form>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
};