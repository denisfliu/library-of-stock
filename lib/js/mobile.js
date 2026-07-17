/* mobile.js — shared mobile UI components for Library of Stock pages.
 *
 * Pairs with the layout switch emitted by lib/render/theme.py:
 * <html data-layout="mobile"|"desktop"> plus a 'loslayout' CustomEvent on
 * every mode change. CSS for the sheet lives in theme.sheet_css().
 *
 * Exposes on window: losLayout, losSheet, losSwipe, losTapTooltips.
 */
(function () {
  'use strict';

  function losLayout() {
    return document.documentElement.dataset.layout || 'desktop';
  }

  /* ---------- bottom sheet ---------- */

  var backdrop = null;
  var openSheet = null;

  function ensureBackdrop() {
    if (backdrop) return backdrop;
    backdrop = document.createElement('div');
    backdrop.className = 'los-backdrop';
    backdrop.addEventListener('click', function () {
      if (openSheet) openSheet.close();
    });
    document.body.appendChild(backdrop);
    return backdrop;
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && openSheet) openSheet.close();
  });

  window.addEventListener('loslayout', function (e) {
    if (e.detail === 'desktop' && openSheet) openSheet.close();
  });

  /* losSheet(el): wire a .los-sheet element (containing a .los-sheet-handle
   * and a .los-sheet-body). Returns {open, close, isOpen, el}. Only one
   * sheet is open at a time; opening another closes the current one. */
  function losSheet(el, opts) {
    opts = opts || {};
    var api = {
      el: el,
      isOpen: function () { return el.classList.contains('open'); },
      open: function () {
        if (openSheet && openSheet !== api) openSheet.close();
        ensureBackdrop().classList.add('open');
        el.classList.add('open');
        document.body.classList.add('los-sheet-open');
        openSheet = api;
        if (opts.onOpen) opts.onOpen();
      },
      close: function () {
        el.classList.remove('open');
        if (backdrop) backdrop.classList.remove('open');
        document.body.classList.remove('los-sheet-open');
        if (openSheet === api) openSheet = null;
        if (opts.onClose) opts.onClose();
      },
      toggle: function () { api.isOpen() ? api.close() : api.open(); }
    };

    // Drag the handle down to dismiss.
    var handle = el.querySelector('.los-sheet-handle');
    if (handle) {
      var startY = null;
      handle.addEventListener('pointerdown', function (e) {
        startY = e.clientY;
        handle.setPointerCapture(e.pointerId);
      });
      handle.addEventListener('pointermove', function (e) {
        if (startY === null) return;
        var dy = e.clientY - startY;
        el.style.transform = dy > 0 ? 'translateY(' + dy + 'px)' : '';
      });
      var endDrag = function (e) {
        if (startY === null) return;
        var dy = e.clientY - startY;
        startY = null;
        el.style.transform = '';
        if (dy > 60) api.close();
      };
      handle.addEventListener('pointerup', endDrag);
      handle.addEventListener('pointercancel', endDrag);
    }
    return api;
  }

  /* ---------- swipe recognizer ---------- */

  /* losSwipe(el, {left, right}): horizontal swipe on el via pointer events.
   * Recognizes |dx| > 60px, |dy| < 40px, duration < 400ms, and only when no
   * text is selected (so selection drags never trigger it). After a
   * recognized swipe the next click on el is swallowed (capture phase) so a
   * trailing synthetic click can't double-fire tap handlers. Handlers only
   * run in mobile layout. */
  function losSwipe(el, handlers) {
    var start = null;
    var swipedAt = 0;
    el.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse') return;
      // A drag that starts in an editable control is a text selection or
      // cursor move, never a navigation gesture.
      if (e.target.closest && e.target.closest('input, textarea, [contenteditable]')) return;
      start = { x: e.clientX, y: e.clientY, t: Date.now() };
    });
    el.addEventListener('pointerup', function (e) {
      if (!start) return;
      var dx = e.clientX - start.x;
      var dy = e.clientY - start.y;
      var dt = Date.now() - start.t;
      start = null;
      if (losLayout() !== 'mobile') return;
      if (Math.abs(dx) <= 60 || Math.abs(dy) >= 40 || dt >= 400) return;
      if (String(window.getSelection ? window.getSelection() : '')) return;
      swipedAt = Date.now();
      if (dx < 0 && handlers.left) handlers.left();
      if (dx > 0 && handlers.right) handlers.right();
    });
    el.addEventListener('pointercancel', function () { start = null; });
    el.addEventListener('click', function (e) {
      if (Date.now() - swipedAt < 500) {
        e.stopPropagation();
        e.preventDefault();
        swipedAt = 0;
      }
    }, true);
  }

  /* ---------- tap tooltips ---------- */

  /* losTapTooltips(sel): in mobile layout, tapping an element matching sel
   * toggles its .open class (CSS shows the tooltip); tapping anywhere else,
   * or the element again, closes it. Desktop hover behavior is untouched. */
  function losTapTooltips(sel) {
    document.addEventListener('click', function (e) {
      if (losLayout() !== 'mobile') return;
      var hit = e.target.closest ? e.target.closest(sel) : null;
      var openEls = document.querySelectorAll(sel + '.open');
      for (var i = 0; i < openEls.length; i++) {
        if (openEls[i] !== hit) openEls[i].classList.remove('open');
      }
      if (hit) {
        hit.classList.toggle('open');
        e.preventDefault();
      }
    });
  }

  window.losLayout = losLayout;
  window.losSheet = losSheet;
  window.losSwipe = losSwipe;
  window.losTapTooltips = losTapTooltips;
})();
