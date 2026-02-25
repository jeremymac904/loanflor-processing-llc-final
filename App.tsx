import React, { useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { Hero } from './components/Hero';
import { Process } from './components/Process';
import { Services } from './components/Services';
import { About } from './components/About';
import { Compliance } from './components/Compliance';
import { Referral } from './components/Referral';
import { LoanSubmission } from './components/LoanSubmission';
import { FAQ } from './components/FAQ';
import { Contact } from './components/Contact';
import { ChatBot } from './components/ChatBot';
import { Footer } from './components/Footer';

function App() {
  
  // Set meta description for SEO (Client-side)
  useEffect(() => {
    document.title = "LoanFlow Processing LLC | High-Tech Mortgage Solutions";
  }, []);

  return (
    <div className="min-h-screen bg-brand-dark selection:bg-brand-copper selection:text-brand-dark">
      <Navbar />
      
      <main>
        <Hero />
        <Process />
        <Services />
        <About />
        <Compliance />
        <Referral />
        <LoanSubmission />
        <FAQ />
        <Contact />
      </main>

      <Footer />
      <ChatBot />
    </div>
  );
}

export default App;