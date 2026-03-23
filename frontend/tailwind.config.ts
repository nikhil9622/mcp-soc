import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./contexts/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sp: {
          bg:      "#1A1E2F",
          surface: "#181B28",
          card:    "#252838",
          hover:   "#2E3245",
          border:  "#3B3D4F",
          green:   "#4AC18E",
          "green-lite": "#68d3a5",
          text:    "#E4E6EB",
          dim:     "#CFD0D3",
          mute:    "#8C8E97",
          white:   "#F9F9F9",
          crit:    "#FF4E4E",
          high:    "#F3973B",
          med:     "#CBBB68",
          low:     "#8C8E97",
          dark:    "#1F2232",
        },
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "monospace"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
      },
      animation: {
        "fade-in": "fadeSlide 0.25s ease-out",
        "pulse-green": "livePulse 2s infinite",
      },
    },
  },
  plugins: [],
};

export default config;
