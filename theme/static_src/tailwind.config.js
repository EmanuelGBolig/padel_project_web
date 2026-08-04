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
    // 'corporate' y 'business' son los que la app setea vía data-theme.
    //
    // 'dark' va incluido a propósito: el bundle del CDN traía un bloque
    //   @media (prefers-color-scheme: dark) { :root { ...tema dark... } }
    // que, al tener la misma especificidad que [data-theme=business] y venir
    // después en el archivo, GANABA. O sea: todo usuario con el sistema en
    // oscuro venía viendo el tema 'dark' (gris azulado), no 'business'
    // (negro neutro), aunque el HTML dijera business.
    // Compilando sólo corporate+business ese override desaparecía y la app se
    // veía más oscura y fría de golpe. Lo dejamos igual que antes.
    themes: ['corporate', 'business', 'dark'],
    logs: false,
  },
}
