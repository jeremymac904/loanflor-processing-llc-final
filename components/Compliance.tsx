import React from 'react';
import { Lock, ShieldAlert, BadgeCheck } from 'lucide-react';

export const Compliance: React.FC = () => {
  return (
    <section className="py-24 bg-[#061210] border-y border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-brand-copper text-[10px] font-bold uppercase tracking-[0.2em] mb-6">
              <Lock size={12} />
              Risk Mitigation
            </div>
            <h2 className="text-3xl md:text-5xl font-serif font-bold bg-gradient-to-b from-white via-white/80 to-white/50 bg-clip-text text-transparent mb-6 leading-tight">
              Compliance Without <br/> The Chaos.
            </h2>
            <p className="text-lg text-gray-400 mb-8 leading-relaxed font-light">
              We don't cut corners. In today's regulatory environment, a "fast" close that triggers an audit isn't a win. We believe in clean, conservative processing.
            </p>

            <div className="space-y-8">
                <div className="flex gap-5 group">
                    <div className="flex-shrink-0 mt-1 w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center border border-white/10 text-brand-copper group-hover:bg-brand-copper group-hover:text-brand-dark transition-colors">
                        <ShieldAlert size={20} />
                    </div>
                    <div>
                        <h4 className="text-white font-bold text-lg mb-1">Strict Guideline Adherence</h4>
                        <p className="text-gray-500 text-sm leading-relaxed">We process strictly to Agency and Lender guidelines. If a file doesn't fit the box, we tell you upfront.</p>
                    </div>
                </div>
                <div className="flex gap-5 group">
                    <div className="flex-shrink-0 mt-1 w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center border border-white/10 text-brand-copper group-hover:bg-brand-copper group-hover:text-brand-dark transition-colors">
                        <BadgeCheck size={20} />
                    </div>
                    <div>
                        <h4 className="text-white font-bold text-lg mb-1">TRID & Regulation Precision</h4>
                        <p className="text-gray-500 text-sm leading-relaxed">Meticulous monitoring of COC events, fee thresholds, and waiting periods to prevent costly cures.</p>
                    </div>
                </div>
            </div>
          </div>

          <div className="relative">
             <div className="absolute inset-0 bg-brand-copper/10 blur-[80px] rounded-full opacity-20"></div>
             
             {/* Glass Panel */}
             <div className="relative rounded-2xl p-8 backdrop-blur-xl bg-white/[0.04] border border-white/10 shadow-[0_1px_0_rgba(255,255,255,0.10),0_22px_70px_rgba(0,0,0,0.60)] ring-1 ring-white/10">
                {/* Inner Depth Overlay */}
                <div className="absolute inset-0 rounded-2xl bg-gradient-to-b from-white/10 via-white/5 to-transparent opacity-60 pointer-events-none"></div>

                {/* Chrome Edge Highlight */}
                <div className="absolute inset-0 rounded-2xl pointer-events-none bg-[linear-gradient(135deg,rgba(255,255,255,0.18),rgba(255,255,255,0.04),rgba(255,255,255,0.14))] opacity-70 mix-blend-overlay"></div>

                <div className="relative z-10">
                    <h3 className="text-xl font-serif text-white mb-8 text-center">Quality Assurance</h3>
                    <div className="space-y-3">
                        <div className="p-4 bg-black/20 rounded-lg border border-white/5 flex justify-between items-center">
                            <span className="text-gray-400 text-sm">Submission Accuracy</span>
                            <span className="text-brand-copper font-mono font-bold">99.8%</span>
                        </div>
                        <div className="p-4 bg-black/20 rounded-lg border border-white/5 flex justify-between items-center">
                            <span className="text-gray-400 text-sm">Stipulation Reduction</span>
                            <span className="text-brand-copper font-mono font-bold">High</span>
                        </div>
                        <div className="p-4 bg-black/20 rounded-lg border border-white/5 flex justify-between items-center">
                            <span className="text-gray-400 text-sm">Cure Resolution</span>
                            <span className="text-brand-copper font-mono font-bold">Proactive</span>
                        </div>
                    </div>
                    <div className="mt-8 pt-6 border-t border-white/5 text-center">
                    <p className="text-[10px] text-gray-500 uppercase tracking-[0.2em]">
                        Your License is Safe With Us
                    </p>
                    </div>
                </div>
             </div>
          </div>

        </div>
      </div>
    </section>
  );
};