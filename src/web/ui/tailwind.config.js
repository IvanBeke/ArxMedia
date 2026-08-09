/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#faf5ff',
          100: '#f3e8ff',
          200: '#e9d5ff',
          300: '#d8b4fe',
          400: '#c084fc',
          500: '#9f42c6',
          600: '#9137b7',
          700: '#7e2fa0',
          800: '#6a2788',
          900: '#562070',
        },
        action: {
          watch: '#9f42c6',
          checkin: '#ed1c24',
          collect: '#16a085',
          list: '#0082ce',
          favorite: '#ffb714',
          watchnow: '#6dc847',
        },
        dark: {
          DEFAULT: '#111111',
          50: '#1a1a1a',
          100: '#1d1d1d',
          200: '#2e2e2e',
          300: '#383838',
          400: '#444444',
        },
        light: {
          DEFAULT: '#ffffff',
          50: '#fafafa',
          100: '#f5f5f5',
          200: '#e5e5e5',
          300: '#d4d4d4',
          400: '#a3a3a3',
        },
        surface: 'var(--bg-surface)',
        'surface-100': 'var(--bg-surface-100)',
        'surface-200': 'var(--bg-surface-200)',
        'surface-300': 'var(--bg-surface-300)',
        primary: 'var(--text-primary)',
        secondary: 'var(--text-secondary)',
        muted: 'var(--text-muted)',
      },
      textColor: {
        primary: 'var(--text-primary)',
        secondary: 'var(--text-secondary)',
        muted: 'var(--text-muted)',
      },
      backgroundColor: {
        surface: 'var(--bg-surface)',
        'surface-100': 'var(--bg-surface-100)',
        'surface-200': 'var(--bg-surface-200)',
        'surface-300': 'var(--bg-surface-300)',
      },
      fontFamily: {
        display: ['"Inter"', 'system-ui', 'sans-serif'],
        body: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
    }
  },
  plugins: []
}
