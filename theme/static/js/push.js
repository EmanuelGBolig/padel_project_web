// TP-11 — Activar/desactivar notificaciones push.
// Requiere un botón #btn-push con data-vapid-key (clave pública) y data-subscribe-url.
// Pide permiso, se suscribe en el service worker y registra la suscripción en el backend.
(function () {
  'use strict';

  var btn = document.getElementById('btn-push');
  if (!btn) return;

  var vapidKey = btn.getAttribute('data-vapid-key') || '';
  var subscribeUrl = btn.getAttribute('data-subscribe-url') || '/accounts/push/subscribe/';
  var csrf = btn.getAttribute('data-csrf') || '';
  var estado = document.getElementById('push-estado');

  var soportado = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;

  function decir(msg, ok) {
    if (!estado) return;
    estado.textContent = msg;
    estado.className = 'text-sm mt-2 ' + (ok ? 'text-success' : 'text-base-content/60');
  }

  function setBoton(activadas) {
    btn.textContent = activadas ? '🔕 Desactivar notificaciones' : '🔔 Activar notificaciones';
    btn.dataset.activadas = activadas ? '1' : '0';
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = window.atob(base64);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; ++i) out[i] = raw.charCodeAt(i);
    return out;
  }

  function postBackend(payload) {
    return fetch(subscribeUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    }).then(function (r) {
      if (!r.ok) throw new Error('No se pudo guardar la suscripción.');
    });
  }

  if (!soportado || !vapidKey) {
    btn.disabled = true;
    if (!vapidKey) decir('Las notificaciones todavía no están habilitadas en el servidor.');
    else decir('Tu navegador no soporta notificaciones. En iPhone: instalá la app primero (Safari → Agregar a inicio) y abrila desde el ícono.');
    return;
  }

  // Estado inicial
  navigator.serviceWorker.ready.then(function (reg) {
    return reg.pushManager.getSubscription();
  }).then(function (sub) {
    setBoton(!!sub);
    if (sub) decir('✅ Las notificaciones están activadas en este dispositivo.', true);
  }).catch(function () {});

  btn.addEventListener('click', function () {
    btn.disabled = true;
    navigator.serviceWorker.ready.then(function (reg) {
      return reg.pushManager.getSubscription().then(function (sub) {
        // --- Desactivar ---
        if (sub && btn.dataset.activadas === '1') {
          var endpoint = sub.endpoint;
          return sub.unsubscribe().then(function () {
            return postBackend({ action: 'unsubscribe', endpoint: endpoint });
          }).then(function () {
            setBoton(false);
            decir('Notificaciones desactivadas en este dispositivo.');
          });
        }
        // --- Activar ---
        return Notification.requestPermission().then(function (perm) {
          if (perm !== 'granted') {
            decir('No diste permiso. Podés activarlo después desde la configuración del navegador.');
            return;
          }
          return reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidKey),
          }).then(function (nueva) {
            var j = nueva.toJSON();
            return postBackend({ endpoint: j.endpoint, keys: j.keys });
          }).then(function () {
            setBoton(true);
            decir('✅ ¡Listo! Vas a recibir avisos de torneos nuevos e invitaciones.', true);
          });
        });
      });
    }).catch(function (e) {
      decir('No se pudo completar: ' + (e && e.message ? e.message : e));
    }).then(function () {
      btn.disabled = false;
    });
  });
})();
