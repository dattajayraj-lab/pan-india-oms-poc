import type { Config } from 'tailwindcss'

// Grid-India OMS design tokens: deep navy brand, saffron accent, cool slate neutrals.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        grid: { 50: '#eef4fb', 100: '#d9e6f5', 200: '#b5cdea', 300: '#86acd9', 400: '#5487c4', 500: '#2f68ad', 600: '#1f5596', 700: '#18467d', 800: '#123766', 900: '#0c2648', 950: '#081a33' },
        saffron: { 50: '#fff6eb', 100: '#ffe7c7', 400: '#f8a443', 500: '#f28c1b', 600: '#d9730b' },
        ink: { 900: '#0f172a', 700: '#334155', 500: '#64748b', 300: '#cbd5e1' },
      },
      fontFamily: { sans: ['Inter', '"Noto Sans Devanagari"', 'system-ui', 'Segoe UI', 'sans-serif'] },
      boxShadow: {
        card: '0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.06)',
        lift: '0 4px 12px rgba(15,23,42,.08), 0 2px 4px rgba(15,23,42,.04)',
      },
      borderRadius: { xl: '0.85rem' },
    },
  },
  plugins: [],
} satisfies Config
