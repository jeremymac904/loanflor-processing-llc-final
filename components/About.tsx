import React from 'react';
import { Quote } from 'lucide-react';
import ashleyHeadshot from '../ashley-headshot.png';

export const About: React.FC = () => {
  return (
    <section id="about" className="py-24 bg-[#122e26]"> {/* Slightly lighter shade */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col lg:flex-row items-center gap-16">
          
          {/* Image/Visual Column */}
          <div className="w-full lg:w-1/2 relative">
             <div className="relative aspect-[3/4] max-w-md mx-auto rounded-2xl overflow-hidden border-2 border-brand-copper/30 shadow-2xl">
                {/* Ashley Rogers Founder Headshot */}
                <img 
                  src={ashleyHeadshot}
                  alt="Ashley Rogers, Founder of LoanFlow Processing" 
                  className="w-full h-full object-cover hover:brightness-110 transition-all duration-700"
                />
                <div className="absolute inset-0 bg-brand-dark/30 mix-blend-multiply"></div>
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-brand-dark to-transparent p-8">
                    <h3 className="text-2xl font-serif font-bold text-white">Ashley Rogers</h3>
                    <p className="text-brand-copper">Owner & Founder</p>
                </div>
             </div>
             {/* Decorative Elements */}
             <div className="absolute -top-6 -left-6 w-24 h-24 border-t-2 border-l-2 border-brand-copper rounded-tl-3xl"></div>
             <div className="absolute -bottom-6 -right-6 w-24 h-24 border-b-2 border-r-2 border-brand-copper rounded-br-3xl"></div>
          </div>

          {/* Text Content */}
          <div className="w-full lg:w-1/2">
            <Quote className="text-brand-copper w-12 h-12 mb-6 opacity-50" />
            <h2 className="text-4xl md:text-5xl font-serif font-bold bg-gradient-to-b from-white via-white/80 to-white/50 bg-clip-text text-transparent mb-6">
              Expertise You Can Trust.
            </h2>
            <p className="text-lg text-gray-300 mb-6 leading-relaxed">
              Founded by Ashley Rogers, LoanFlow Processing LLC was built on the principle that mortgage processing should be seamless, not stressful. 
            </p>
            <p className="text-lg text-gray-300 mb-8 leading-relaxed">
              With years of industry experience, Ashley understands the nuances of the lending landscape. She has cultivated a workflow that prioritizes clear communication, speed, and accuracy, ensuring that Brokers can scale their business without getting bogged down in paperwork.
            </p>
            
            <div className="flex flex-col space-y-4">
               <div className="flex items-center gap-4 p-4 bg-brand-dark/50 rounded-lg border border-brand-medium/30">
                  <div className="w-2 h-2 rounded-full bg-brand-copper"></div>
                  <p className="text-gray-200">Personalized attention for every file.</p>
               </div>
               <div className="flex items-center gap-4 p-4 bg-brand-dark/50 rounded-lg border border-brand-medium/30">
                  <div className="w-2 h-2 rounded-full bg-brand-copper"></div>
                  <p className="text-gray-200">Deep knowledge of Agency & Non-QM guidelines.</p>
               </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
};