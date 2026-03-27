import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        dark: {
          bg: "#0C0A09",
          card: "#1C1917",
          surface: "#292524",
          border: "#3D3530",
        },
        text: {
          primary: "#FAFAF9",
          secondary: "#D6D3D1",
          muted: "#A8A29E",
        },
        fashion: {
          gold: "#D4A853",
          "gold-light": "#E8C878",
          "gold-dark": "#B8922F",
          rose: "#BE123C",
          "rose-light": "#FB7185",
          cream: "#FFFBEB",
        },
        brand: {
          solid: "#D4A853",
          "solid-hover": "#B8922F",
        },
        status: {
          success: "#22C55E",
          warning: "#F59E0B",
          error: "#EF4444",
        },
      },
      fontFamily: {
        arabic: ['"IBM Plex Sans Arabic"', "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
