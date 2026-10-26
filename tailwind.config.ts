import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: { extend: { colors: { echo: { bg: "#080e18", mint: "#63e0c9" } } } },
  plugins: [],
};
export default config;
