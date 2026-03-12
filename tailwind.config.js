/** @type {import('tailwindcss').Config} */
import defaultTheme from 'tailwindcss/defaultTheme';

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', ...defaultTheme.fontFamily.sans],
        mono: ['JetBrains Mono', ...defaultTheme.fontFamily.mono],
      },
      colors: {
        // Deep Charcoal Backgrounds
        background: {
          DEFAULT: '#0F1115', // Main app background
          panel: '#15181E',   // Card/panel background
          accent: '#1C1F26',  // Hover states, active tabs
        },
        // Professional Text Colors
        content: {
          primary: '#FFFFFF',
          secondary: '#9CA3AF',
          muted: '#6B7280',
        },
        // Semantic Financial Colors (Muted, Professional)
        bullish: {
          DEFAULT: '#10B981', // Muted Emerald
          muted: 'rgba(16, 185, 129, 0.15)', // For tinted backgrounds
        },
        bearish: {
          DEFAULT: '#E11D48', // Sharp Crimson
          muted: 'rgba(225, 29, 72, 0.15)', // For tinted backgrounds
        },
        warning: {
          DEFAULT: '#F59E0B',
          muted: 'rgba(245, 158, 11, 0.15)',
        },
        border: '#272A30' // Ultra-thin panel borders
      },
      boxShadow: {
        'glow-bullish': '0 0 20px rgba(16, 185, 129, 0.15)',
        'glow-bearish': '0 0 20px rgba(225, 29, 72, 0.15)',
      }
    },
  },
  plugins: [],
}
