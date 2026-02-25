import React from 'react';
import { UploadCloud, FileSearch, CheckSquare, MessageCircle, Gavel } from 'lucide-react';

const steps = [
  {
    id: 1,
    title: "Submission & Intake",
    description: "You submit a clean file. We perform immediate audit and initial disclosures within 24 hours.",
    icon: <UploadCloud className="w-5 h-5 text-brand-dark" />
  },
  {
    id: 2,
    title: "AUS & Setup",
    description: "AUS findings, verification orders, title, and appraisals initiated immediately.",
    icon: <FileSearch className="w-5 h-5 text-brand-dark" />
  },
  {
    id: 3,
    title: "Conditions",
    description: "We anticipate and clear underwriting conditions. We chase the stips, not you.",
    icon: <CheckSquare className="w-5 h-5 text-brand-dark" />
  },
  {
    id: 4,
    title: "Communication",
    description: "Scheduled updates for Borrowers and LOs. No uncomfortable 'need more docs' calls.",
    icon: <MessageCircle className="w-5 h-5 text-brand-dark" />
  },
  {
    id: 5,
    title: "CTC & Funding",
    description: "We balance the CD, coordinate with title, and ensure a compliant funding package.",
    icon: <Gavel className="w-5 h-5 text-brand-dark" />
  }
];

export const Process: React.FC = () => {
  return (
    <section id="process" className="py-24 bg-[#0a1f1b] relative border-y border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        <div className="text-center mb-20">
          <span className="text-brand-copper uppercase tracking-[0.2em] text-xs font-bold">The Workflow</span>
          <h2 className="mt-3 text-3xl md:text-5xl font-serif font-bold bg-gradient-to-b from-white via-white/80 to-white/50 bg-clip-text text-transparent">How We Operate</h2>
          <p className="text-gray-400 mt-4 max-w-2xl mx-auto font-light">
            Standardized. Predictable. Chaos-free.
          </p>
        </div>

        <div className="relative">
          {/* Chrome Divider - Connecting Line */}
          <div className="hidden md:block absolute top-8 left-0 w-full h-px bg-gradient-to-r from-transparent via-white/15 to-transparent z-0"></div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-6 relative z-10">
            {steps.map((step, index) => (
              <div key={step.id} className="flex flex-col items-center text-center group">
                
                {/* Step Icon with Metallic Ring */}
                <div className="w-16 h-16 rounded-full bg-gradient-to-b from-[#d4b08c] to-[#a67c52] flex items-center justify-center mb-6 shadow-[0_0_20px_rgba(198,156,109,0.15)] group-hover:scale-105 transition-transform duration-500 relative z-10 border border-white/20">
                  {step.icon}
                  <div className="absolute -top-2 -right-2 w-6 h-6 bg-[#0a1f1b] border border-brand-medium/50 rounded-full flex items-center justify-center text-[10px] text-brand-copper font-bold">
                    {step.id}
                  </div>
                </div>

                <h3 className="text-white font-serif font-bold text-lg mb-3">{step.title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed px-2">
                  {step.description}
                </p>
              </div>
            ))}
          </div>
        </div>

      </div>
    </section>
  );
};