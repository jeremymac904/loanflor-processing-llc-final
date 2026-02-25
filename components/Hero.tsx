import React from 'react';
import { ArrowRight, ShieldCheck, Zap, BarChart3 } from 'lucide-react';

export const Hero: React.FC = () => {
  const handleScroll = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    const element = document.getElementById(id);
    if (element) {
      const headerOffset = 80;
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.scrollY - headerOffset;

      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      });
    }
  };

  return (
    <section id="home" className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20">
      
      {/* Background Elements - Deeper, more luxurious */}
      <div className="absolute inset-0 bg-[#081613] z-0">
        <div className="absolute top-0 left-0 w-full h-[80%] bg-[radial-gradient(circle_at_50%_0%,rgba(198,156,109,0.08),transparent_70%)]"></div>
        <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] bg-[#0f2822] blur-[150px] rounded-full opacity-40"></div>
      </div>

      {/* Refined Grid Overlay */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:60px_60px] z-0 pointer-events-none opacity-20"></div>

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col items-center text-center">
        
        {/* Glass Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 backdrop-blur-md text-brand-copper text-[10px] font-bold uppercase tracking-[0.2em] mb-10 shadow-[inset_0_1px_0_rgba(255,255,255,0.1)] hover:bg-white/10 transition-colors cursor-default">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500"></span>
          </span>
          Serving Florida Brokers <span className="opacity-50 mx-1">|</span> More States Coming Soon
        </div>

        {/* Main Heading - Sharpened & Tighter */}
        <h1 className="text-5xl md:text-7xl lg:text-8xl font-serif font-bold mb-8 tracking-tight leading-[0.95]">
          <span className="bg-gradient-to-b from-white via-white/80 to-white/50 bg-clip-text text-transparent">
            Precision Processing.
          </span><br/>
          <span className="bg-gradient-to-b from-[#caa35a] via-[#b8893f] to-[#8f6a2f] bg-clip-text text-transparent">
            Zero Friction.
          </span>
        </h1>

        <p className="max-w-2xl text-lg md:text-xl text-gray-400 mb-12 leading-relaxed font-light">
          We own the workflow from intake to funding. You focus on origination.
          <span className="block mt-4 text-gray-200 font-normal">Predictable timelines. Zero drag. Total Compliance.</span>
        </p>
        
        {/* Call to Actions - Metallic & Glass */}
        <div className="flex flex-col sm:flex-row gap-5 w-full sm:w-auto">
          {/* Copper Metallic Button (Primary) */}
          <a 
            href="#contact" 
            onClick={(e) => handleScroll(e, 'contact')}
            className="group relative inline-flex items-center justify-center gap-2 rounded-xl px-6 py-3 font-medium bg-gradient-to-b from-[#caa35a] via-[#b8893f] to-[#8f6a2f] shadow-[0_1px_0_rgba(255,255,255,0.18),0_20px_55px_rgba(0,0,0,0.60)] text-black/90 transition duration-300 hover:brightness-110 active:brightness-95"
          >
             {/* Specular highlight overlay */}
             <span className="absolute inset-0 rounded-xl pointer-events-none bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.55),rgba(255,255,255,0)_55%)] opacity-60"></span>
             
             <span className="relative z-10 flex items-center gap-2 tracking-wide">
                Start Processing
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
             </span>
          </a>

          {/* Chrome Button (Secondary) */}
          <a 
            href="#contact" 
            onClick={(e) => handleScroll(e, 'contact')}
            className="group relative inline-flex items-center justify-center gap-2 rounded-xl px-6 py-3 bg-white/[0.06] backdrop-blur-xl border border-white/15 ring-1 ring-white/10 shadow-[0_1px_0_rgba(255,255,255,0.12),0_18px_45px_rgba(0,0,0,0.55)] text-white/90 hover:text-white transition duration-300 hover:bg-white/[0.10] hover:border-white/20 hover:ring-white/15"
          >
            {/* Inner highlight overlay */}
            <span className="absolute inset-0 rounded-xl pointer-events-none bg-gradient-to-b from-white/20 via-white/5 to-transparent opacity-60"></span>
            Request Callback
          </a>
        </div>

        {/* Feature Highlights - Glass Cards */}
        <div className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-6 text-left w-full max-w-6xl">
          {[
            { icon: <Zap className="text-brand-copper" strokeWidth={1.5} />, title: "Velocity", desc: "Proactive condition management for faster clear-to-close." },
            { icon: <ShieldCheck className="text-brand-copper" strokeWidth={1.5} />, title: "Compliance", desc: "Audit-ready files. Strict adherence to agency guidelines." },
            { icon: <BarChart3 className="text-brand-copper" strokeWidth={1.5} />, title: "Visibility", desc: "Real-time pipeline updates. You never lose control." },
          ].map((feature, idx) => (
            <div key={idx} className="group relative rounded-2xl p-8 backdrop-blur-xl bg-white/[0.04] border border-white/10 shadow-[0_1px_0_rgba(255,255,255,0.10),0_22px_70px_rgba(0,0,0,0.60)] ring-1 ring-white/10 transition duration-300 hover:bg-white/[0.06] hover:border-white/15 hover:shadow-[0_1px_0_rgba(255,255,255,0.14),0_26px_90px_rgba(0,0,0,0.70)] overflow-hidden">
              
              {/* Inner Depth Overlay */}
              <div className="absolute inset-0 rounded-2xl bg-gradient-to-b from-white/10 via-white/5 to-transparent opacity-60 pointer-events-none group-hover:opacity-80 transition-opacity"></div>
              
              {/* Chrome Edge Highlight */}
              <div className="absolute inset-0 rounded-2xl pointer-events-none bg-[linear-gradient(135deg,rgba(255,255,255,0.18),rgba(255,255,255,0.04),rgba(255,255,255,0.14))] opacity-70 mix-blend-overlay"></div>

              <div className="relative z-10 w-10 h-10 rounded-lg bg-gradient-to-br from-white/10 to-transparent flex items-center justify-center mb-6 border border-white/5 text-brand-copper shadow-inner">
                {feature.icon}
              </div>
              <h3 className="relative z-10 text-lg font-serif font-bold text-white mb-2">{feature.title}</h3>
              <p className="relative z-10 text-gray-400 text-sm leading-relaxed group-hover:text-gray-300 transition-colors">{feature.desc}</p>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
};