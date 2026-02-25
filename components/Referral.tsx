import React, { useState } from 'react';
import { Users, UserPlus, CheckCircle, Sparkles } from 'lucide-react';

export const Referral: React.FC = () => {
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    // Simulate API call
    setTimeout(() => {
      setIsSubmitting(false);
      setSubmitted(true);
    }, 1500);
  };

  if (submitted) {
    return (
      <section id="referrals" className="py-24 bg-brand-medium/10 border-y border-brand-medium/30 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(198,156,109,0.05),transparent_70%)]"></div>
        <div className="max-w-3xl mx-auto px-4 text-center relative z-10 animate-fade-in-up">
            <div className="w-24 h-24 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-8 border border-green-500/30 shadow-[0_0_30px_rgba(34,197,94,0.2)]">
              <CheckCircle className="w-12 h-12 text-green-500" />
            </div>
            <h3 className="text-4xl font-serif font-bold bg-gradient-to-b from-white via-white/80 to-white/50 bg-clip-text text-transparent mb-6">Referral Received</h3>
            <p className="text-xl text-gray-300 mb-10 leading-relaxed">
              Thank you for trusting LoanFlow. We will reach out to your referral shortly with the same level of care and professionalism you expect from us.
            </p>
            {/* Chrome Button (Secondary) */}
            <button 
              onClick={() => setSubmitted(false)} 
              className="relative inline-flex items-center justify-center gap-2 rounded-xl px-6 py-3 bg-white/[0.06] backdrop-blur-xl border border-white/15 ring-1 ring-white/10 shadow-[0_1px_0_rgba(255,255,255,0.12),0_18px_45px_rgba(0,0,0,0.55)] text-white/90 hover:text-white transition duration-300 hover:bg-white/[0.10] hover:border-white/20 hover:ring-white/15"
            >
              <span className="absolute inset-0 rounded-xl pointer-events-none bg-gradient-to-b from-white/20 via-white/5 to-transparent opacity-60"></span>
              Send Another Referral
            </button>
        </div>
      </section>
    );
  }

  return (
    <section id="referrals" className="py-24 bg-gradient-to-b from-[#0b1f1a] to-brand-dark relative">
      {/* Decorative background elements */}
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-brand-medium to-transparent"></div>
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center mb-16">
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-copper/10 border border-brand-copper/30 text-brand-copper text-xs font-semibold uppercase tracking-widest mb-4">
            <Sparkles size={12} />
            Partner Program
          </span>
          <h2 className="text-4xl md:text-5xl font-serif font-bold bg-gradient-to-b from-white via-white/80 to-white/50 bg-clip-text text-transparent mb-6">Grow the Network</h2>
          <p className="mt-4 text-gray-400 max-w-2xl mx-auto text-lg">
            Know a mortgage broker struggling with processing capacity? <br/>
            Refer them to <span className="bg-gradient-to-b from-[#caa35a] via-[#b8893f] to-[#8f6a2f] bg-clip-text text-transparent font-bold">LoanFlow</span>.
          </p>
        </div>

        {/* Glass Panel */}
        <div className="relative rounded-2xl p-8 md:p-12 backdrop-blur-xl bg-white/[0.04] border border-white/10 shadow-[0_1px_0_rgba(255,255,255,0.10),0_22px_70px_rgba(0,0,0,0.60)] ring-1 ring-white/10 overflow-hidden">
          {/* Inner Depth Overlay */}
          <div className="absolute inset-0 rounded-2xl bg-gradient-to-b from-white/10 via-white/5 to-transparent opacity-60 pointer-events-none"></div>
          
          {/* Chrome Edge Highlight */}
          <div className="absolute inset-0 rounded-2xl pointer-events-none bg-[linear-gradient(135deg,rgba(255,255,255,0.18),rgba(255,255,255,0.04),rgba(255,255,255,0.14))] opacity-70 mix-blend-overlay"></div>

          {/* Subtle grid pattern on card */}
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.01)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.01)_1px,transparent_1px)] bg-[size:20px_20px] pointer-events-none"></div>

          <form onSubmit={handleSubmit} className="relative z-10 grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-12">
            
            {/* Left Column: Referrer */}
            <div className="space-y-6">
                <div className="flex items-center gap-3 border-b border-brand-medium/50 pb-4 mb-2">
                    <Users className="text-brand-copper w-6 h-6" />
                    <h3 className="text-xl font-bold text-white">Your Information</h3>
                </div>
                
                <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">Your Name</label>
                    <input required type="text" className="w-full bg-brand-medium/20 border border-brand-medium/50 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-copper focus:ring-1 focus:ring-brand-copper transition-all placeholder-gray-600" placeholder="e.g. Ashley Rogers" />
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">Your Email</label>
                    <input required type="email" className="w-full bg-brand-medium/20 border border-brand-medium/50 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-copper focus:ring-1 focus:ring-brand-copper transition-all placeholder-gray-600" placeholder="you@brokerage.com" />
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">Relationship to Referral</label>
                    <select className="w-full bg-brand-medium/20 border border-brand-medium/50 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-copper focus:ring-1 focus:ring-brand-copper transition-all">
                        <option className="bg-brand-dark">Colleague</option>
                        <option className="bg-brand-dark">Friend</option>
                        <option className="bg-brand-dark">Professional Network</option>
                        <option className="bg-brand-dark">Other</option>
                    </select>
                </div>
            </div>

            {/* Right Column: Referee */}
            <div className="space-y-6">
                <div className="flex items-center gap-3 border-b border-brand-medium/50 pb-4 mb-2">
                    <UserPlus className="text-brand-copper w-6 h-6" />
                    <h3 className="text-xl font-bold text-white">Referral Information</h3>
                </div>
                
                <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">Broker Name</label>
                    <input required type="text" className="w-full bg-brand-medium/20 border border-brand-medium/50 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-copper focus:ring-1 focus:ring-brand-copper transition-all placeholder-gray-600" placeholder="e.g. John Doe" />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-400 mb-2">Broker Phone</label>
                        <input type="tel" className="w-full bg-brand-medium/20 border border-brand-medium/50 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-copper focus:ring-1 focus:ring-brand-copper transition-all placeholder-gray-600" placeholder="(555) 123-4567" />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-400 mb-2">Broker Email</label>
                        <input required type="email" className="w-full bg-brand-medium/20 border border-brand-medium/50 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-copper focus:ring-1 focus:ring-brand-copper transition-all placeholder-gray-600" placeholder="john@company.com" />
                    </div>
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">Notes (Optional)</label>
                    <textarea rows={2} className="w-full bg-brand-medium/20 border border-brand-medium/50 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-copper focus:ring-1 focus:ring-brand-copper transition-all placeholder-gray-600" placeholder="Any specific needs?"></textarea>
                </div>
            </div>

            {/* Submit Button (Primary) */}
            <div className="md:col-span-2 pt-6 flex justify-center">
                <button 
                  type="submit" 
                  disabled={isSubmitting}
                  className="w-full md:w-auto min-w-[300px] relative inline-flex items-center justify-center gap-2 rounded-xl px-6 py-3 font-medium bg-gradient-to-b from-[#caa35a] via-[#b8893f] to-[#8f6a2f] shadow-[0_1px_0_rgba(255,255,255,0.18),0_20px_55px_rgba(0,0,0,0.60)] text-black/90 transition duration-300 hover:brightness-110 active:brightness-95 disabled:opacity-70 disabled:cursor-not-allowed"
                >
                  {/* Specular highlight overlay */}
                  <span className="absolute inset-0 rounded-xl pointer-events-none bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.55),rgba(255,255,255,0)_55%)] opacity-60"></span>
                  
                  {isSubmitting ? 'Sending...' : 'Submit Referral'}
                </button>
            </div>

          </form>
        </div>
      </div>
    </section>
  );
};