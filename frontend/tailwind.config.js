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
          50: '#f0eff7',
          100: '#e2dbf7',
          200: '#c5bff0',
          300: '#a8a3e8',
          400: '#8b87e0',
          500: '#7169d5',
          600: '#5d54c0',
          700: '#4b4aa3',
          800: '#3d3d82',
          900: '#323779',
          950: '#152249',
        },
        dark: {
          50: '#e8eaf0',
          100: '#c5c9d6',
          200: '#9ea5b8',
          300: '#78809a',
          400: '#5b6484',
          500: '#3e486e',
          600: '#364066',
          700: '#2c355b',
          800: '#1e2640',
          900: '#111827',
          950: '#0a0e1a',
        },
        accent: {
          peach: '#e9aa93',
          lightPeach: '#f5dcc9',
          darkPeach: '#d4907a',
        },
        status: {
          operational: '#7169d5',
          warning: '#e9aa93',
          critical: '#ef4444',
          offline: '#6b7280',
          maintenance: '#8b5cf6',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'slide-in-up': 'slideInUp 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideInRight: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        slideInUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
