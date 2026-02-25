import { GoogleGenAI, Chat, GenerateContentResponse } from "@google/genai";
import { SYSTEM_INSTRUCTION } from "../constants";

let chatSession: Chat | null = null;
let genAI: GoogleGenAI | null = null;

const getAIInstance = (): GoogleGenAI => {
  if (!genAI) {
    if (!process.env.API_KEY) {
      throw new Error("API Key not found");
    }
    genAI = new GoogleGenAI({ apiKey: process.env.API_KEY });
  }
  return genAI;
};

export const initializeChat = async (): Promise<Chat> => {
  const ai = getAIInstance();
  chatSession = ai.chats.create({
    model: 'gemini-3-flash-preview',
    config: {
      systemInstruction: SYSTEM_INSTRUCTION,
      temperature: 0.7,
    },
  });
  return chatSession;
};

export const sendMessageToAI = async (message: string): Promise<string> => {
  try {
    if (!chatSession) {
      await initializeChat();
    }
    
    if (!chatSession) {
        throw new Error("Failed to initialize chat session");
    }

    const result: GenerateContentResponse = await chatSession.sendMessage({
      message: message
    });

    return result.text || "I apologize, I didn't catch that. Could you rephrase?";
  } catch (error) {
    console.error("Gemini API Error:", error);
    return "I'm currently experiencing high traffic. Please reach out to Ashley directly at (904) 535-1902.";
  }
};