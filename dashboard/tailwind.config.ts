import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "rgb(var(--background) / <alpha-value>)",
        foreground: "rgb(var(--foreground) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        bull: "rgb(var(--bull) / <alpha-value>)",
        bear: "rgb(var(--bear) / <alpha-value>)",
        premium: "rgb(var(--premium) / <alpha-value>)",
      },
    },
  },
  plugins: [],
};
export default config;
