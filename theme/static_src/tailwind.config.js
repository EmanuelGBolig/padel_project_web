/** Tailwind v3 compilado — reemplaza el CDN (cdn.tailwindcss.com).
 *  DaisyUI sigue cargándose por su CDN (no genera warning). Misma config que tenía
 *  el CDN inline: darkMode por clase, fuente Inter y primary esmeralda. */
module.exports = {
  content: [
    '../../core/**/*.{html,py}',
    '../../accounts/**/*.{html,py}',
    '../../equipos/**/*.{html,py}',
    '../../torneos/**/*.{html,py}',
    '../../padel_project/**/*.py',
    '../../theme/templates/**/*.html',
    '../../templates/**/*.html',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      colors: {
        primary: '#10b981', // Emerald 500
      },
    },
  },
  plugins: [],
}
