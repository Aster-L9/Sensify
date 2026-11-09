/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0eff9',
          100: '#e2dff6',
          200: '#c7c2ef',
          300: '#a9a3e6',
          400: '#8c85dd',
          500: '#7169d5',
          600: '#5b52c2',
          700: '#4a42a6',
          800: '#3b3584',
          900: '#2f2b69',
          950: '#1b1940',
        },
        // A cool, navy-leaning grey so every existing gray-* utility shares the new ink.
        gray: {
          50: '#f6f7fa',
          100: '#eef0f5',
          200: '#e3e5ed',
          300: '#cdd0dc',
          400: '#a2a7bb',
          500: '#7c8199',
          600: '#5d6280',
          700: '#4a4f68',
          800: '#2f3350',
          900: '#191c33',
          950: '#0f1124',
        },
        canvas: '#f1f2f6',
        rule: '#e3e5ed',
        ink: { DEFAULT: '#191c33', 2: '#4a4f68', 3: '#7c8199' },
        accent: {
          peach: '#e9aa93',
          lightPeach: '#f5dcc9',
          darkPeach: '#d4907a',
        },
        status: {
          operational: '#7169d5',
          warning: '#d97706',
          critical: '#b91c1c',
          offline: '#7c8199',
          maintenance: '#8b5cf6',
        },
      },
      fontFamily: {
        // One family. Numbers use tabular figures (see globals.css) instead of a monospace face.
        sans: ['Archivo', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['Archivo', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      borderRadius: {
        sheet: '16px',
      },
      boxShadow: {
        sheet: '0 1px 2px rgba(25, 28, 51, 0.04), 0 0 0 1px rgba(25, 28, 51, 0.04)',
        lift: '0 12px 32px -12px rgba(25, 28, 51, 0.22), 0 0 0 1px rgba(25, 28, 51, 0.05)',
      },
      transitionTimingFunction: {
        out: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.24s cubic-bezier(0.22, 1, 0.36, 1)',
        'page-in': 'pageIn 0.36s cubic-bezier(0.22, 1, 0.36, 1)',
        'slide-in-right': 'slideInRight 0.32s cubic-bezier(0.22, 1, 0.36, 1)',
        'slide-in-up': 'slideInUp 0.3s cubic-bezier(0.22, 1, 0.36, 1)',
        'pop-in': 'popIn 0.22s cubic-bezier(0.22, 1, 0.36, 1)',
        'expand': 'expand 0.28s cubic-bezier(0.22, 1, 0.36, 1)',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        pageIn: {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        slideInUp: {
          '0%': { transform: 'translateY(16px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        popIn: {
          '0%': { transform: 'translateY(-4px) scale(0.98)', opacity: '0' },
          '100%': { transform: 'translateY(0) scale(1)', opacity: '1' },
        },
        expand: {
          '0%': { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
