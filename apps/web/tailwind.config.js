/** Tailwind maps every colour to a CSS token (src/styles/tokens.css), so dark mode is a token swap. */
const token = (name) => `var(--${name})`;

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        "surface-2": token("surface-2"),
        border: token("border"),
        text: token("text"),
        muted: token("text-muted"),
        sidebar: token("sidebar"),
        "sidebar-text": token("sidebar-text"),
        primary: token("primary"),
        "primary-hover": token("primary-hover"),
        "on-primary": token("on-primary"),
        accent: token("accent"),
        "focus-ring": token("focus-ring"),
        quote: token("quote-bg"),
        danger: token("danger"),
        "danger-bg": token("danger-bg"),
        pass: { DEFAULT: token("pass"), bg: token("pass-bg") },
        fail: { DEFAULT: token("fail"), bg: token("fail-bg") },
        flaky: { DEFAULT: token("flaky"), bg: token("flaky-bg") },
        blocked: { DEFAULT: token("blocked"), bg: token("blocked-bg") },
        testerr: { DEFAULT: token("testerr"), bg: token("testerr-bg") },
        uv: { DEFAULT: token("uv"), bg: token("uv-bg") },
        sev: {
          critical: token("sev-critical"),
          high: token("sev-high"),
          medium: token("sev-medium"),
          low: token("sev-low"),
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: { DEFAULT: "8px", card: "12px" },
    },
  },
  plugins: [],
};
