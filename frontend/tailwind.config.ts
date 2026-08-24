import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0f172a",
        panel: "#1e293b",
      },
    },
  },
  plugins: [],
};

export default config;
