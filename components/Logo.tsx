import React from 'react';

export const Logo: React.FC<{ className?: string }> = ({ className = "" }) => {
  return (
    <div className={`flex flex-col items-center justify-center leading-none select-none ${className}`}>
      <div className="relative mb-1">
         {/* Simulating the LF Monogram */}
         <span className="font-serif text-5xl font-bold text-brand-copper tracking-tighter relative z-10">L</span>
         <span className="font-serif text-5xl font-bold text-brand-medium absolute left-4 top-1 -z-0">F</span>
      </div>
      <h1 className="font-serif text-2xl font-bold text-brand-medium tracking-wide">
        Loan<span className="text-brand-copper">Flow</span>
      </h1>
      <p className="text-[0.6rem] uppercase tracking-[0.2em] text-brand-copper mt-1">
        Processing LLC
      </p>
    </div>
  );
};