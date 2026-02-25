import React, { useState, useMemo } from 'react';
import { ChevronDown, Sparkles } from 'lucide-react';

const faqs = [
  {
    question: "What specific loan types do you process?",
    answer: "We specialize in Conventional (Fannie/Freddie), FHA, VA, USDA, and select Non-QM products. We are experienced with both refinance and purchase transactions. Please note that we strictly adhere to lender guidelines; we do not process 'grey area' files."
  },
  {
    question: "What remains the Broker's responsibility?",
    answer: "You are responsible for the initial origination: taking the application, pulling credit, structuring the loan, and locking the rate. Once you have a signed intent to proceed and a complete submission package, we take over the processing operations."
  },
  {
    question: "How do you handle borrower communication?",
    answer: "We take a proactive lead. We introduce ourselves as your dedicated processing team immediately upon file receipt. We handle all document collection and status updates. You are CC'd on every email, so you maintain visibility without needing to manage the thread."
  },
  {
    question: "What LOS platforms are you compatible with?",
    answer: "We are platform-agnostic. We work directly within your instance of Encompass, Calyx Point, LendingPad, or ARIVE. This ensures that you own your data and have real-time access to the file status 24/7."
  },
  {
    question: "How does your fee structure work?",
    answer: "We operate on a standard 3rd party processing fee paid at closing via the ALTA/CD. It is a 'success fee' model—if the loan does not close, we do not get paid. This aligns our incentives perfectly with yours."
  }
];

export const FAQ: React.FC = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const toggleFAQ = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  // Generate stable particles for background effect
  const particles = useMemo(() => {
    return Array.from({ length: 30 }).map((_, i) => ({
      id: i,
      left: Math.random() * 100,
      top: Math.random() * 100,
      size: Math.random() * 3 + 1,
      duration: Math.random() * 20 + 15,
      delay: Math.random() * 5,
      opacity: Math.random() * 0.3 + 0.1,
      moveX: (Math.random() - 0.5) * 50,
      moveY: -100 - Math.random() * 50
    }));
  }, []);

  return (
    <section id="faq" className="py-32 relative overflow-hidden bg-[#081613]">
      {/* CSS for custom animations */}
      <style>{`
        @keyframes float-slow {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -50px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
        }
        @keyframes float-slower {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(-30px, 50px) scale(1.1); }
          66% { transform: translate(20px, -20px) scale(0.95); }
        }
        @keyframes particle-drift {
            0% { transform: translate(0, 0); opacity: 0; }
            20% { opacity: var(--opacity); }
            80% { opacity: var(--opacity); }
            100% { transform: translate(var(--move-x), var(--move-y)); opacity: 0; }
        }
        .animate-float-slow { animation: float-slow 18s ease-in-out infinite; }
        .animate-float-slower { animation: float-slower 24s ease-in-out infinite; }
        .animate-particle { animation: particle-drift linear infinite; }
      `}</style>

      {/* Luxurious Animated Background */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
          {/* Deep Radial Gradients for Depth */}
          <div className="absolute top-[-20%] left-[-10%] w-[70%] h-[70%] bg-brand-medium/20 rounded-full blur-[120px] animate-float-slow mix-blend-screen opacity-50"></div>
          <div className="absolute bottom-[-20%] right-[-10%] w-[70%] h-[70%] bg-brand-copper/10 rounded-full blur-[120px] animate-float-slower mix-blend-screen opacity-50"></div>
          
          {/* Subtle Tech Grid Pattern */}
          <div className="absolute inset-0 bg-[linear-gradient(rgba(198,156,109,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(198,156,109,0.03)_1px,transparent_1px)] bg-[size:80px_80px] opacity-20 mask-image:radial-gradient(ellipse_at_center,black,transparent)"></div>

          {/* Floating Golden Particles */}
          {particles.map((p) => (
             <div 
               key={p.id}
               className="absolute rounded-full bg-brand-copper animate-particle"
               style={{
                 left: `${p.left}%`,
                 top: `${p.top}%`,
                 width: `${p.size}px`,
                 height: `${p.size}px`,
                 '--opacity': p.opacity,
                 '--move-x': `${p.moveX}px`,
                 '--move-y': `${p.moveY}px`,
                 animationDuration: `${p.duration}s`,
                 animationDelay: `${p.delay}s`,
               } as React.CSSProperties} 
             />
          ))}

          {/* Noise Texture for Film Grain/Premium Feel */}
          <div className="absolute inset-0 opacity-[0.02] mix-blend-overlay" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }}></div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center mb-20">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-gradient-to-r from-brand-medium/40 to-brand-dark border border-brand-copper/30 text-brand-copper text-xs font-bold uppercase tracking-[0.2em] mb-6 shadow-[0_0_15px_rgba(198,156,109,0.15)] backdrop-blur-md">
            <Sparkles size={12} />
            <span>Broker Intelligence</span>
          </div>
          <h2 className="text-4xl md:text-6xl font-serif font-bold bg-gradient-to-b from-white via-white/80 to-white/50 bg-clip-text text-transparent mb-6 tracking-tight drop-shadow-lg">
            Frequently Asked <br/>
            <span className="bg-gradient-to-b from-[#caa35a] via-[#b8893f] to-[#8f6a2f] bg-clip-text text-transparent animate-pulse-slow">
              Questions
            </span>
          </h2>
          <p className="text-gray-400 text-lg font-light tracking-wide max-w-2xl mx-auto leading-relaxed">
            Clarifying the operational details so you can make an informed decision.
          </p>
        </div>

        <div className="space-y-6">
          {faqs.map((faq, index) => {
            const isOpen = openIndex === index;
            return (
              <div 
                key={index} 
                className={`relative group rounded-2xl transition-all duration-500 ${
                  isOpen 
                    ? 'bg-gradient-to-b from-brand-medium/30 to-brand-dark/50 border-brand-copper/40 shadow-[0_0_30px_rgba(0,0,0,0.3)]' 
                    : 'bg-brand-medium/10 border-white/5 hover:bg-brand-medium/20 hover:border-brand-copper/20'
                } border backdrop-blur-md`}
              >
                {/* Glow effect on active */}
                {isOpen && <div className="absolute inset-0 bg-brand-copper/5 rounded-2xl pointer-events-none blur-sm"></div>}

                <button
                  onClick={() => toggleFAQ(index)}
                  className="relative w-full flex items-center justify-between p-8 text-left focus:outline-none z-10"
                >
                  <span className={`font-serif text-xl transition-colors duration-300 ${isOpen ? 'text-brand-copper font-medium' : 'text-gray-200 group-hover:text-white'}`}>
                    {faq.question}
                  </span>
                  <div className={`
                    flex items-center justify-center w-8 h-8 rounded-full border transition-all duration-500
                    ${isOpen 
                        ? 'bg-brand-copper border-brand-copper text-brand-dark rotate-180 shadow-[0_0_10px_rgba(198,156,109,0.4)]' 
                        : 'bg-transparent border-gray-600 text-gray-400 group-hover:border-brand-copper group-hover:text-brand-copper'}
                  `}>
                    <ChevronDown size={16} strokeWidth={2.5} />
                  </div>
                </button>
                
                <div 
                  className={`relative z-10 grid transition-[grid-template-rows] duration-500 ease-[cubic-bezier(0.4,0,0.2,1)] ${
                    isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
                  }`}
                >
                  <div className="overflow-hidden">
                    <div className="px-8 pb-8 pt-0 text-gray-400 leading-relaxed font-light text-lg">
                      {/* Chrome Divider */}
                      <div className="h-px w-full bg-gradient-to-r from-transparent via-white/15 to-transparent mb-6"></div>
                      {faq.answer}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};