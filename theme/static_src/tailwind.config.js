/** Tailwind v3 + DaisyUI, ambos compilados en el build.
 *
 *  Antes DaisyUI se cargaba desde jsDelivr con `full.min.css`: ese bundle trae los
 *  30+ temas (~190 KB sin comprimir) para usar dos, y mete un origen externo en el
 *  camino crítico del render. Compilándolo acá entran solo los temas y las clases
 *  que la app realmente usa.
 */
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
  // Clases que el escáner NO puede ver porque se arman al renderizar.
  // `alert-{{ message.tags }}` (accounts/complete_profile.html) es el caso real:
  // el sufijo lo pone Django, no está literal en ningún archivo.
  safelist: [
    'alert-success',
    'alert-error',
    'alert-warning',
    'alert-info',
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
  plugins: [require('daisyui')],
  daisyui: {
    // Solo los dos temas que usa la app. base.html sobrescribe las variables de
    // "corporate" con tripletes oklch (ver ARQUITECTURA.md).
    themes: ['corporate', 'business'],
    logs: false,
  },
}
