import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1f2933",
        line: "#d8dee8",
        field: "#0f766e",
        court: "#d97706",
        review: "#2563eb",
        alert: "#be123c"
      },
      boxShadow: {
        panel: "0 12px 30px rgba(31, 41, 51, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;

