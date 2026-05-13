import type { Config } from 'tailwindcss'

export default {
  content: ['./src/renderer/**/*.{ts,tsx}', './src/renderer/index.html'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: 'oklch(18% 0.005 85)',           // warm dark base
          elevated: 'oklch(22% 0.005 85)',           // sidebar, cards
          overlay: 'oklch(26% 0.005 85)',            // hover, dropdowns
          highlight: 'oklch(30% 0.005 85)',          // active selections
        },
        text: {
          primary: 'oklch(92% 0.005 85)',            // warm off-white
          secondary: 'oklch(72% 0.005 85)',          // muted warm gray
          muted: 'oklch(50% 0.005 85)',              // tertiary
        },
        accent: {
          DEFAULT: 'oklch(65% 0.19 40)',             // warm orange (#f54e00 mapped)
          muted: 'oklch(52% 0.15 40)',
          hover: 'oklch(70% 0.19 40)',
        },
        // Pipeline stage colors — Cursor's timeline palette
        stage: {
          planner: 'oklch(68% 0.08 35)',             // warm peach — "thinking"
          coder: 'oklch(62% 0.12 160)',              // sage green — "grep/search"
          reviewer: 'oklch(62% 0.08 250)',           // soft blue — "read"
          merge: 'oklch(62% 0.1 300)',               // soft lavender — "edit"
        },
        status: {
          running: 'oklch(68% 0.18 140)',
          error: 'oklch(62% 0.18 20)',               // warm crimson
          suspended: 'oklch(65% 0.12 80)',
          pending: 'oklch(45% 0.01 85)',
          stopped: 'oklch(40% 0.01 85)',
        },
      },
      fontFamily: {
        mono: ['BerkeleyMono', 'JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        pill: '9999px',
      },
      animation: {
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
        'slide-up': 'slide-up 0.25s ease-out',
        'fade-in': 'fade-in 0.2s ease-out',
        'scale-in': 'scale-in 0.2s ease-out',
      },
      keyframes: {
        'pulse-dot': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.96)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
      },
    },
  },
  plugins: [],
} satisfies Config
