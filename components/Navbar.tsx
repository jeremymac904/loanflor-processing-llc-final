import React, { useState, useEffect } from 'react';
import { Menu, X, Phone, Send } from 'lucide-react';

export const Navbar: React.FC = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Scroll detection is preserved for functionality (like closing menu on scroll if desired), 
  // but visual styling is now handled by the permanent glass classes as per spec.
  useEffect(() => {
    const handleScroll = () => {
      // Logic if needed in future
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { name: 'Home', href: '#home' },
    { name: 'Services', href: '#services' },
    { name: 'Process', href: '#process' },
    { name: 'Referrals', href: '#referrals' },
    { name: 'FAQ', href: '#faq' },
    { name: 'Contact', href: '#contact' },
  ];

  // Primary CTA link styled as a button
  const submitLink = { name: 'Submit Loan', href: '#submit' };

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    e.preventDefault();
    const targetId = href.replace('#', '');
    const element = document.getElementById(targetId);
    
    if (element) {
      const headerOffset = 80;
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.scrollY - headerOffset;

      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      });
    }
    setIsMobileMenuOpen(false);
  };

  return (
    <nav className="fixed top-0 inset-x-0 z-50 backdrop-blur-xl bg-black/40 border-b border-white/10 shadow-[0_1px_0_rgba(255,255,255,0.08),0_18px_50px_rgba(0,0,0,0.65)] ring-1 ring-white/5">
      {/* Chrome edge overlay */}
      <span className="absolute inset-0 pointer-events-none bg-[linear-gradient(180deg,rgba(255,255,255,0.14),rgba(255,255,255,0.03),rgba(0,0,0,0.25))] opacity-70"></span>

      {/* Inner wrapper */}
      <div className="relative mx-auto max-w-7xl flex h-16 items-center justify-between px-6">
          
          {/* Logo Section */}
          <div className="flex items-center gap-2 cursor-pointer group" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
             <div className="flex items-center gap-3">
                <span className="font-serif text-3xl font-bold bg-gradient-to-b from-white via-white/80 to-white/60 bg-clip-text text-transparent group-hover:opacity-80 transition-opacity">LF</span>
                <div className="hidden md:flex flex-col leading-none">
                    <span className="font-serif text-lg font-semibold tracking-wide bg-gradient-to-b from-white via-white/80 to-white/60 bg-clip-text text-transparent">Loan<span className="text-brand-copper">Flow</span></span>
                    <span className="text-[0.4rem] text-white/50 uppercase tracking-[0.3em]">Processing LLC</span>
                </div>
             </div>
          </div>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-6">
            {navLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                onClick={(e) => handleNavClick(e, link.href)}
                className="relative text-sm font-medium text-white/70 transition duration-200 hover:text-white uppercase tracking-wider after:absolute after:-bottom-2 after:left-0 after:h-px after:w-full after:bg-gradient-to-r after:from-transparent after:via-white/40 after:to-transparent after:opacity-0 hover:after:opacity-100"
              >
                {link.name}
              </a>
            ))}
             
             {/* Divider */}
             <div className="h-4 w-px bg-white/10 mx-2"></div>

             {/* Submit Loan CTA */}
             <a
               href={submitLink.href}
               onClick={(e) => handleNavClick(e, submitLink.href)}
               className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-brand-copper to-amber-600 px-4 py-1.5 text-xs font-bold text-brand-dark uppercase tracking-wider transition-all duration-200 hover:shadow-lg hover:shadow-brand-copper/25 hover:scale-[1.03] active:scale-[0.97]"
             >
               <Send className="h-3 w-3" />
               {submitLink.name}
             </a>

             {/* Phone Link */}
             <a
              href="tel:9045351902"
              className="flex items-center gap-2 text-xs text-white/60 hover:text-white/85 transition"
            >
              <Phone className="h-4 w-4 text-white/40" />
              <span className="font-bold tracking-wider">(904) 535-1902</span>
            </a>
          </div>

          {/* Mobile Menu Button */}
          <div className="md:hidden flex items-center">
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="inline-flex items-center justify-center rounded-lg p-2 bg-white/[0.05] backdrop-blur border border-white/10 ring-1 ring-white/5 text-white/80 hover:bg-white/[0.10] transition"
            >
              {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
      </div>

      {/* Mobile Menu Panel */}
      {isMobileMenuOpen && (
        <div className="absolute top-full left-0 right-0 px-4 pb-4">
          <div className="mt-2 rounded-2xl backdrop-blur-xl bg-black/60 border border-white/10 ring-1 ring-white/5 shadow-[0_22px_70px_rgba(0,0,0,0.75)] overflow-hidden">
            <div className="px-4 py-4 space-y-1">
              {navLinks.map((link) => (
                <a
                  key={link.name}
                  href={link.href}
                  onClick={(e) => handleNavClick(e, link.href)}
                  className="block px-3 py-3 rounded-lg text-sm font-medium text-white/70 hover:text-white hover:bg-white/5 transition-all uppercase tracking-wider"
                >
                  {link.name}
                </a>
              ))}
               <div className="border-t border-white/10 my-2"></div>
               <a
                 href={submitLink.href}
                 onClick={(e) => handleNavClick(e, submitLink.href)}
                 className="flex items-center gap-2 px-3 py-3 rounded-lg text-sm font-bold text-brand-copper hover:bg-brand-copper/10 transition-all uppercase tracking-wider"
               >
                 <Send className="h-4 w-4" />
                 <span>{submitLink.name}</span>
               </a>
               <a
                href="tel:9045351902"
                className="flex items-center gap-2 px-3 py-3 text-sm font-medium text-white/70 hover:text-white hover:bg-white/5 transition-all"
              >
                <Phone className="h-4 w-4 text-white/40" />
                <span>(904) 535-1902</span>
              </a>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
};