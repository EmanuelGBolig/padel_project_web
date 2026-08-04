/*
 * TP-01 — Botón de compartir.
 * Mejora progresiva sobre el partial partials/_share_button.html:
 *  - Si el navegador soporta la Web Share API, muestra "Compartir…" (ideal en mobile).
 *  - "Copiar link" usa la Clipboard API con fallback a execCommand.
 *  - El link de WhatsApp es un <a> y funciona aunque este script no cargue.
 */
(function () {
    'use strict';

    function getShareData(el) {
        var root = el.closest('[data-share]');
        if (!root) {
            return null;
        }
        return {
            url: root.getAttribute('data-share-url') || window.location.href,
            title: root.getAttribute('data-share-title') || document.title,
            text: root.getAttribute('data-share-text') || ''
        };
    }

    function fallbackCopy(text, done) {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
        } catch (e) { /* noop */ }
        document.body.removeChild(ta);
        if (done) {
            done();
        }
    }

    function flashCopied(btn) {
        var label = btn.querySelector('.js-share-copy-label');
        if (!label) {
            return;
        }
        if (!label.getAttribute('data-original')) {
            label.setAttribute('data-original', label.textContent);
        }
        label.textContent = '¡Link copiado!';
        setTimeout(function () {
            label.textContent = label.getAttribute('data-original');
        }, 2000);
    }

    document.addEventListener('DOMContentLoaded', function () {
        // Mostrar la opción de compartir nativo solo si el navegador la soporta.
        if (navigator.share) {
            document.querySelectorAll('.js-share-native').forEach(function (el) {
                el.classList.remove('hidden');
            });
        }
    });

    document.addEventListener('click', function (e) {
        var nativeBtn = e.target.closest('.js-share-native');
        if (nativeBtn) {
            e.preventDefault();
            var d = getShareData(nativeBtn);
            if (d && navigator.share) {
                navigator.share({ title: d.title, text: d.text, url: d.url }).catch(function () { /* cancelado */ });
            }
            return;
        }

        var copyBtn = e.target.closest('.js-share-copy');
        if (copyBtn) {
            e.preventDefault();
            var data = getShareData(copyBtn);
            if (!data) {
                return;
            }
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(data.url).then(function () {
                    flashCopied(copyBtn);
                }).catch(function () {
                    fallbackCopy(data.url, function () { flashCopied(copyBtn); });
                });
            } else {
                fallbackCopy(data.url, function () { flashCopied(copyBtn); });
            }
        }
    });
})();
