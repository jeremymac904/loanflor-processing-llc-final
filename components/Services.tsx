import React from 'react';
import { CheckCircle2, FileCheck } from 'lucide-react';

const ServiceCard: React.FC<{ title: string; description: string; items: string[] }> = ({ title, description, items }) => (
  <div className="group relative rounded-2xl p-8 h-full flex flex-col overflow-hidden backdrop-blur-xl bg-white/[0.04] border border-white/10 shadow-[0_1px_0_rgba(255,255,255,0.10),0_22px_70px_rgba(0,0,0,0.60)] ring-1 ring-white/10 transition duration-300 hover:bg-white/[0.06] hover:border-white/15 hover:shadow-[0_1px_0_rgba(255,255,255,0.14),0_26px_90px_rgba(0,0,0,0.70)]">
    
    {/* Inner Depth Overlay */}
    <div className="absolute inset-0 rounded-2xl bg-gradient-to-b from-white/10 via-white/5 to-transparent opacity-60 pointer-events-none"></div>

    {/* Chrome Edge Highlight */}
    <div className="absolute inset-0 rounded-2xl pointer-events-none bg-[linear-gradient(135deg,rgba(255,255,255,0.18),rgba(255,255,255,0.04),rgba(255,255,255,0.14))] opacity-70 mix-blend-overlay"></div>

    <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity z-0">
      <FileCheck size={100} className="text-brand-copper" />
    </div>
    
    <div className="relative z-10 flex flex-col h-full">
        <h3 className="text-2xl font-serif font-bold text-white mb-4">{title}</h3>
        <p className="text-gray-400 mb-8 flex-grow font-light leading-relaxed">{description}</p>
        
        <div className="mt-auto">
            {/* Chrome Divider */}
            <div className="h-px w-full bg-gradient-to-r from-transparent via-white/15 to-transparent mb-6"></div>
            
            <p className="text-brand-copper text-[10px] uppercase tracking-[0.2em] mb-4 font-bold">Ownership</p>
            <ul className="space-y-3">
            {items.map((item, idx) => (
                <li key={idx} className="flex items-start gap-3">
                <CheckCircle2 className="w-4 h-4 text-brand-copper/80 flex-shrink-0 mt-0.5" />
                <span className="text-gray-300 text-sm">{item}</span>
                </li>
            ))}
            </ul>
        </div>
    </div>
  </div>
);

export const Services: React.FC = () => {
  return (
    <section id="services" className="py-24 bg-brand-dark relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        <div className="text-center mb-16">
          <span className="text-brand-copper uppercase tracking-[0.2em] text-xs font-bold">Scope of Work</span>
          <h2 className="mt-3 text-4xl md:text-5xl font-serif font-bold bg-gradient-to-b from-white via-white/80 to-white/50 bg-clip-text text-transparent">We Own The Process</h2>
          <div className="h-0.5 w-16 bg-brand-copper/50 mx-auto mt-6"></div>
          <p className="mt-4 text-gray-400 max-w-2xl mx-auto font-light">
            Total responsibility from contract to funding.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ServiceCard 
            title="Operational Execution"
            description="Stop chasing documents. We take the administrative burden off your plate so you can focus on bringing in new business."
            items={[
              "Complete file setup & initial disclosures",
              "Ordering Title, Appraisals, VOEs & HOI",
              "Direct clearing of Underwriting conditions",
              "Coordination of closing with Title & Lender",
              "Balancing the CD & Scheduling signing"
            ]}
          />
           <ServiceCard 
            title="Risk & Compliance Management"
            description="We act as your compliance firewall. We ensure every file meets lender guidelines before submission, reducing suspense conditions."
            items={[
              "Rigorous pre-submission audit",
              "TRID timeline monitoring & management",
              "State-specific compliance checks",
              "Prior-to-doc (PTD) & Prior-to-funding (PTF) review",
              "Post-closing deficiency resolution"
            ]}
          />
        </div>

        {/* Stats Section - Metallic Bar */}
        <div className="mt-20 relative bg-gradient-to-r from-white/[0.02] to-white/[0.05] rounded-2xl p-8 md:p-12 border border-white/5 flex flex-col md:flex-row justify-around items-center gap-8 backdrop-blur-sm shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] overflow-hidden">
            <div className="absolute inset-0 bg-white/5 opacity-20 pointer-events-none"></div>
            <div className="relative z-10 text-center">
                <div className="text-4xl font-serif font-bold text-brand-copper mb-2">Zero</div>
                <div className="text-gray-400 text-xs uppercase tracking-[0.2em]">Acceptable Errors</div>
            </div>
            <div className="relative z-10 h-px w-full md:h-12 md:w-px bg-white/10"></div>
            <div className="relative z-10 text-center">
                <div className="text-4xl font-serif font-bold text-brand-copper mb-2">24h</div>
                <div className="text-gray-400 text-xs uppercase tracking-[0.2em]">Turnaround Standard</div>
            </div>
            <div className="relative z-10 h-px w-full md:h-12 md:w-px bg-white/10"></div>
            <div className="relative z-10 text-center">
                <div className="text-4xl font-serif font-bold text-brand-copper mb-2">100%</div>
                <div className="text-gray-400 text-xs uppercase tracking-[0.2em]">File Ownership</div>
            </div>
        </div>
      </div>
    </section>
  );
};