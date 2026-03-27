import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#111111',
          card: '#1C1C1E',
          surface: '#2A2A2E',
          border: '#333333',
          'border-light': '#444444',
        },
        text: {
          primary: '#FFFFFF',
          secondary: '#AAAAAA',
          muted: '#555555',
        },
        brand: {
          solid: '#1A1A2E',
          'solid-hover': '#252540',
        },
        status: {
          success: '#4CAF50',
          warning: '#FF9800',
          star: '#FFB800',
        },
        sikka: {
          gold: '#FFB800',
          dark: '#111111',
          gray: '#AAAAAA',
        },
      },
      fontFamily: {
        arabic: ['"IBM Plex Sans Arabic"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
export default config
